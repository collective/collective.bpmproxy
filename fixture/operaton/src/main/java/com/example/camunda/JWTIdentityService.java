package com.example.camunda;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.source.JWKSource;
import com.nimbusds.jose.jwk.source.RemoteJWKSet;
import com.nimbusds.jose.proc.JWSVerificationKeySelector;
import com.nimbusds.jose.proc.SecurityContext;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.proc.ConfigurableJWTProcessor;
import com.nimbusds.jwt.proc.DefaultJWTClaimsVerifier;
import com.nimbusds.jwt.proc.DefaultJWTProcessor;
import org.operaton.bpm.engine.impl.IdentityServiceImpl;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.net.MalformedURLException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.text.ParseException;
import java.util.List;
import java.util.Set;


public class JWTIdentityService extends IdentityServiceImpl {

    /**
     * Claim carrying the fixed Operaton username a Keycloak client
     * impersonates (a "Hardcoded Claim" protocol mapper on the client, e.g.
     * the {@code operaton-worker} service-account client mapping to
     * {@code admin}). Interactive logins carry no such claim and fall back
     * to {@code preferred_username}, then {@code sub}.
     */
    static final String OPERATON_USERNAME_CLAIM = "operaton_username";

    private static final Logger log = LoggerFactory.getLogger(JWTIdentityService.class);

    private String publicKey;
    private boolean oauth2Enabled;
    private String keycloakIssuerUri;
    private ConfigurableJWTProcessor<SecurityContext> keycloakJwtProcessor;

    public void setPublicKey(String publicKey) {
        this.publicKey = publicKey;
    }

    public String getPublicKey() {
        if (publicKey == null || publicKey.isEmpty()) {
            // Unconfigured: fail closed and legibly rather than throwing a
            // NullPointerException out of the authentication filter.
            log.warn("No plone.public-key configured; JWT authentication is disabled.");
            return null;
        }
        File f = new File(publicKey);
        if (f.exists()) {
            try {
                return Files.readString(Paths.get(publicKey), StandardCharsets.US_ASCII);
            } catch (IOException e) {
                log.warn(e.toString());
                return null;
            }
        } else {
            return publicKey;
        }
    }

    public void setOAuth2Enabled(boolean oauth2Enabled) {
        this.oauth2Enabled = oauth2Enabled;
    }

    public boolean isOAuth2Enabled() {
        return oauth2Enabled;
    }

    /**
     * Builds the JWKS-backed JWT processor once, from the realm's
     * {@code /protocol/openid-connect/certs} endpoint. {@link RemoteJWKSet}
     * fetches and caches keys lazily on first use, so this does no network
     * call itself; a malformed issuer URI fails closed (null processor, no
     * Keycloak token will ever verify) rather than throwing at startup.
     */
    public void setKeycloakIssuerUri(String keycloakIssuerUri) {
        this.keycloakIssuerUri = keycloakIssuerUri;
        if (keycloakIssuerUri == null || keycloakIssuerUri.isEmpty()) {
            this.keycloakJwtProcessor = null;
            return;
        }
        try {
            JWKSource<SecurityContext> keySource =
                    new RemoteJWKSet<>(new URL(keycloakIssuerUri + "/protocol/openid-connect/certs"));
            DefaultJWTProcessor<SecurityContext> processor = new DefaultJWTProcessor<>();
            processor.setJWSKeySelector(new JWSVerificationKeySelector<>(JWSAlgorithm.RS256, keySource));
            // Requires exp (fail-closed, same as JWTTokens for Plone tokens)
            // and pins the issuer -- this realm is dedicated to this
            // deployment, so issuer + signature + expiry is the intended
            // amount of checking; audience/azp is deliberately not enforced.
            processor.setJWTClaimsSetVerifier(new DefaultJWTClaimsVerifier<>(
                    new JWTClaimsSet.Builder().issuer(keycloakIssuerUri).build(),
                    Set.of("exp")));
            this.keycloakJwtProcessor = processor;
        } catch (MalformedURLException e) {
            log.warn("Invalid keycloak issuer-uri {}; Keycloak JWT authentication is disabled.", keycloakIssuerUri);
            this.keycloakJwtProcessor = null;
        }
    }

    /**
     * @return the verified claims, or {@code null} if OAuth2 isn't enabled,
     *         no processor is configured, or the token is absent, malformed,
     *         wrongly signed, expired, or issued by another realm.
     */
    JWTClaimsSet verifyKeycloakToken(String token) {
        if (!oauth2Enabled || keycloakJwtProcessor == null || token == null || token.isEmpty()) {
            return null;
        }
        try {
            return keycloakJwtProcessor.process(token, null);
        } catch (Exception e) {
            log.debug("Rejecting unverifiable Keycloak JWT: {}", e.toString());
            return null;
        }
    }

    private static String resolveKeycloakUsername(JWTClaimsSet claims) {
        try {
            String username = claims.getStringClaim(OPERATON_USERNAME_CLAIM);
            if (username != null && !username.isEmpty()) {
                return username;
            }
            username = claims.getStringClaim("preferred_username");
            if (username != null && !username.isEmpty()) {
                return username;
            }
        } catch (ParseException e) {
            log.warn("Verified Keycloak JWT carries an unusable username claim: {}", e.toString());
        }
        return claims.getSubject();
    }

    /**
     * @return the token's {@code groups} claim (the realm's
     *         {@code oidc-group-membership-mapper}, the same mapper that
     *         already backs Cockpit's own OAuth2 login), or {@code null} if
     *         absent/unusable -- in which case the engine falls back to
     *         whatever persistent group membership the resolved username
     *         already has, same as Basic Auth.
     */
    private static List<String> resolveKeycloakGroups(JWTClaimsSet claims) {
        try {
            return claims.getStringListClaim("groups");
        } catch (ParseException e) {
            log.warn("Verified Keycloak JWT carries an unusable groups claim: {}", e.toString());
            return null;
        }
    }

    @Override
    public void setAuthentication(String userId, List<String> groups, List<String> tenantIds) {
        // Transient JWT. Verify it here rather than assuming the REST
        // authentication filter was the only way in: this method is reachable
        // from other code paths, and claims from an unverified token must
        // never reach the engine's identity.
        JWTClaimsSet claims = JWTTokens.verify(userId, getPublicKey());
        if (claims != null) {
            try {
                super.setAuthentication(
                        claims.getStringClaim("sub"),
                        claims.getStringListClaim("groups"),
                        claims.getStringListClaim("tenant_ids"));
                return;
            } catch (ParseException e) {
                log.warn("Verified JWT carries unusable claims: {}", e.toString());
            }
        }

        // Transient Keycloak JWT, re-verified for the same reason. Resolves
        // to a *persistent* Operaton user (the realm's group-membership
        // claim, same as Cockpit's own OAuth2 login already uses -- unlike
        // the Plone branch, which asserts groups directly since Plone
        // identities aren't persistent engine users at all).
        JWTClaimsSet keycloakClaims = verifyKeycloakToken(userId);
        if (keycloakClaims != null) {
            super.setAuthentication(
                    resolveKeycloakUsername(keycloakClaims),
                    resolveKeycloakGroups(keycloakClaims),
                    null);
            return;
        }

        // Persistent Basic Auth
        super.setAuthentication(userId, groups, tenantIds);
    }
}

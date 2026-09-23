package com.example.camunda;

import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.io.pem.PemObject;
import org.bouncycastle.util.io.pem.PemReader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.StringReader;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.Security;
import java.security.Signature;
import java.security.spec.X509EncodedKeySpec;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Parsing and verification of the ed25519-signed JWTs that Plone sends to
 * {@code /engine-rest/*}.
 *
 * <p>Verification is deliberately shared by {@link JWTAuthenticationProvider}
 * and {@link JWTIdentityService}: the identity service must never trust claims
 * from a token it has not verified itself, since it is reachable from more than
 * one code path.
 *
 * <p>A token is accepted only if all of the following hold:
 * <ul>
 *   <li>the JWS header algorithm is EdDSA (no algorithm substitution);</li>
 *   <li>the signature verifies against the configured public key;</li>
 *   <li>an {@code exp} claim is present and has not passed;</li>
 *   <li>{@code nbf}, when present, is not in the future.</li>
 * </ul>
 * Requiring {@code exp} is a deliberate fail-closed choice: Plone always sets
 * it, so a token without one did not come from a supported client.
 */
public final class JWTTokens {

    /** Tolerance for clock skew between Plone and the engine. */
    static final long CLOCK_SKEW_SECONDS = 60;

    private static final Logger log = LoggerFactory.getLogger(JWTTokens.class);

    /**
     * Parsed keys, cached by PEM text. Parsing is pure and the key set is
     * tiny and bounded by configuration, so this never needs eviction.
     */
    private static final Map<String, PublicKey> KEY_CACHE = new ConcurrentHashMap<>();

    static {
        // Registering the provider is idempotent, and doing it once here keeps
        // it out of the per-request path.
        if (Security.getProvider(BouncyCastleProvider.PROVIDER_NAME) == null) {
            Security.addProvider(new BouncyCastleProvider());
        }
    }

    private JWTTokens() {
    }

    /**
     * @return the verified claims, or {@code null} if the token is absent,
     *         malformed, wrongly signed, expired or not yet valid.
     */
    public static JWTClaimsSet verify(String token, String publicKeyPem) {
        if (token == null || token.isEmpty() || publicKeyPem == null || publicKeyPem.isEmpty()) {
            return null;
        }
        try {
            SignedJWT jwt = SignedJWT.parse(token);

            JWSAlgorithm algorithm = jwt.getHeader().getAlgorithm();
            if (!JWSAlgorithm.EdDSA.equals(algorithm)) {
                log.debug("Rejecting JWT with unexpected algorithm: {}", algorithm);
                return null;
            }

            if (!isSignatureValid(token, publicKeyPem)) {
                log.debug("JWT signature validation failed.");
                return null;
            }

            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            if (!isTimeValid(claims)) {
                return null;
            }
            return claims;
        } catch (Exception e) {
            log.debug("Rejecting unparseable or unverifiable JWT: {}", e.toString());
            return null;
        }
    }

    private static boolean isSignatureValid(String token, String publicKeyPem) throws Exception {
        String[] parts = token.split("\\.");
        if (parts.length < 3) {
            return false;
        }
        Signature signature = Signature.getInstance("EdDSA", BouncyCastleProvider.PROVIDER_NAME);
        signature.initVerify(publicKey(publicKeyPem));
        signature.update((parts[0] + "." + parts[1]).getBytes());
        return signature.verify(Base64.getUrlDecoder().decode(parts[2]));
    }

    private static boolean isTimeValid(JWTClaimsSet claims) throws java.text.ParseException {
        Instant now = Instant.now();

        Date expiration = claims.getExpirationTime();
        if (expiration == null) {
            log.debug("Rejecting JWT without an exp claim.");
            return false;
        }
        if (expiration.toInstant().plusSeconds(CLOCK_SKEW_SECONDS).isBefore(now)) {
            log.debug("Rejecting JWT that expired at {}.", expiration);
            return false;
        }

        Date notBefore = claims.getNotBeforeTime();
        if (notBefore != null && notBefore.toInstant().minusSeconds(CLOCK_SKEW_SECONDS).isAfter(now)) {
            log.debug("Rejecting JWT that is not valid before {}.", notBefore);
            return false;
        }
        return true;
    }

    /** Parse (and cache) an ed25519 public key from PEM text. */
    static PublicKey publicKey(String pem) throws Exception {
        PublicKey cached = KEY_CACHE.get(pem);
        if (cached != null) {
            return cached;
        }
        PemObject pemObject;
        try (PemReader reader = new PemReader(new StringReader(pem))) {
            pemObject = reader.readPemObject();
        }
        if (pemObject == null) {
            throw new IllegalArgumentException("Configured public key is not valid PEM");
        }
        KeyFactory keyFactory = KeyFactory.getInstance("EdDSA", BouncyCastleProvider.PROVIDER_NAME);
        PublicKey parsed = keyFactory.generatePublic(new X509EncodedKeySpec(pemObject.getContent()));
        KEY_CACHE.put(pem, parsed);
        return parsed;
    }
}

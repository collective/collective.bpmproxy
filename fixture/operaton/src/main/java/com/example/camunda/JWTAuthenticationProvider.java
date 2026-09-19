package com.example.camunda;

import org.operaton.bpm.engine.ProcessEngine;
import org.operaton.bpm.engine.rest.security.auth.AuthenticationResult;
import org.operaton.bpm.engine.rest.security.auth.impl.HttpBasicAuthenticationProvider;
import org.springframework.http.HttpHeaders;

import jakarta.servlet.http.HttpServletRequest;


public class JWTAuthenticationProvider extends HttpBasicAuthenticationProvider {

    protected static final String TOKEN_AUTH_HEADER_PREFIX = "Bearer ";

    @Override
    public AuthenticationResult extractAuthenticatedUser(HttpServletRequest request,
                                                         ProcessEngine engine) {

        // Transient JWT -- Plone is always tried first, in every mode. Only
        // touches the engine's identity service once we know there is a
        // bearer token to check, matching the Basic branch below.
        String authorizationHeader = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (authorizationHeader != null && authorizationHeader.startsWith(TOKEN_AUTH_HEADER_PREFIX)) {
            String token = authorizationHeader.substring(TOKEN_AUTH_HEADER_PREFIX.length());
            JWTIdentityService identityService = (JWTIdentityService) engine.getIdentityService();

            // Verifies the signature *and* the exp/nbf claims; see JWTTokens.
            // The engine carries this value into JWTIdentityService.setAuthentication,
            // which verifies it again rather than trusting it.
            if (JWTTokens.verify(token, identityService.getPublicKey()) != null) {
                return AuthenticationResult.successful(token);
            }

            // Keycloak JWT: only tried in the mode where Operaton's own
            // webapp login is configured for it, and re-verified by
            // setAuthentication for the same reason as the Plone branch above.
            if (identityService.isOAuth2Enabled() && identityService.verifyKeycloakToken(token) != null) {
                return AuthenticationResult.successful(token);
            }

            return AuthenticationResult.unsuccessful();
        }

        // Persistent Basic Auth and Keycloak JWT are mutually exclusive:
        // a successful Basic result is only honored in the mode where
        // Keycloak isn't the configured login mechanism.
        AuthenticationResult result = super.extractAuthenticatedUser(request, engine);
        if (result.getAuthenticatedUser() != null) {
            JWTIdentityService identityService = (JWTIdentityService) engine.getIdentityService();
            if (!identityService.isOAuth2Enabled()) {
                return result;
            }
            return AuthenticationResult.unsuccessful();
        }

        return AuthenticationResult.unsuccessful();
    }
}

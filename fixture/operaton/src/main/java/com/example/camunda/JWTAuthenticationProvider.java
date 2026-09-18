package com.example.camunda;

import com.nimbusds.jwt.JWTClaimsSet;
import org.operaton.bpm.engine.ProcessEngine;
import org.operaton.bpm.engine.IdentityService;
import org.operaton.bpm.engine.rest.security.auth.AuthenticationResult;
import org.operaton.bpm.engine.rest.security.auth.impl.HttpBasicAuthenticationProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpHeaders;

import jakarta.servlet.http.HttpServletRequest;


public class JWTAuthenticationProvider extends HttpBasicAuthenticationProvider {

    protected static final String TOKEN_AUTH_HEADER_PREFIX = "Bearer ";

    private static final Logger log = LoggerFactory.getLogger(JWTAuthenticationProvider.class);

    @Override
    public AuthenticationResult extractAuthenticatedUser(HttpServletRequest request,
                                                         ProcessEngine engine) {

        // Persistent Basic Auth
        AuthenticationResult result = super.extractAuthenticatedUser(request, engine);
        if (result.getAuthenticatedUser() != null) {
            return result;
        }

        // Transient JWT
        String authorizationHeader = request.getHeader(HttpHeaders.AUTHORIZATION);
        if (authorizationHeader == null || !authorizationHeader.startsWith(TOKEN_AUTH_HEADER_PREFIX)) {
            return result;
        }
        String token = authorizationHeader.substring(TOKEN_AUTH_HEADER_PREFIX.length());

        IdentityService identityService = engine.getIdentityService();
        String publicKey = ((JWTIdentityService) identityService).getPublicKey();

        // Verifies the signature *and* the exp/nbf claims; see JWTTokens.
        JWTClaimsSet claims = JWTTokens.verify(token, publicKey);
        if (claims == null) {
            return result;
        }

        // The engine carries this value into JWTIdentityService.setAuthentication,
        // which verifies it again rather than trusting it.
        return AuthenticationResult.successful(token);
    }
}

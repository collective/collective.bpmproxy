package com.example.camunda;

import com.nimbusds.jose.JOSEException;
import com.nimbusds.jose.JWSVerifier;
import com.nimbusds.jose.crypto.ECDSAVerifier;
import com.nimbusds.jose.jwk.ECKey;
import com.nimbusds.jose.jwk.JWK;
import com.nimbusds.jwt.SignedJWT;
import io.micronaut.http.HttpHeaders;
import org.camunda.bpm.engine.IdentityService;
import org.camunda.bpm.engine.ProcessEngine;
import org.camunda.bpm.engine.rest.security.auth.AuthenticationResult;
import org.camunda.bpm.engine.rest.security.auth.impl.HttpBasicAuthenticationProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.servlet.http.HttpServletRequest;
import java.text.ParseException;


public class JWTAuthenticationProvider extends HttpBasicAuthenticationProvider {

    protected static final String TOKEN_AUTH_HEADER_PREFIX = "Bearer ";

    private static final Logger log = LoggerFactory.getLogger(JWTAuthenticationProvider.class);

    @Override
    public AuthenticationResult extractAuthenticatedUser(HttpServletRequest request,
                                                         ProcessEngine engine) {

        // Persistent Basic Auth
        AuthenticationResult result = super.extractAuthenticatedUser(request, engine);

        // Transient JWT
        if (result.getAuthenticatedUser() == null) {
            IdentityService identityService = engine.getIdentityService();
            String publicKey = ((JWTIdentityService) identityService).getPublicKey();
            String authorizationHeader = request.getHeader(HttpHeaders.AUTHORIZATION);
            if (authorizationHeader != null && authorizationHeader.startsWith(TOKEN_AUTH_HEADER_PREFIX)) {
                String token = authorizationHeader.substring(TOKEN_AUTH_HEADER_PREFIX.length());
                try {
                    JWK key = JWK.parseFromPEMEncodedObjects(publicKey);
                    SignedJWT jwt = SignedJWT.parse(token);
                    JWSVerifier verifier = new ECDSAVerifier((ECKey) key);
                    if (jwt.verify(verifier)) {
                        return AuthenticationResult.successful(token);
                    }
                } catch (ParseException | JOSEException e) {
                    // No op.
                }
            }
        }

        return result;
    }
}


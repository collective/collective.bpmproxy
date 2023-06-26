package com.example.camunda;

import io.micronaut.http.HttpHeaders;
import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.io.pem.PemObject;
import org.bouncycastle.util.io.pem.PemReader;
import org.camunda.bpm.engine.IdentityService;
import org.camunda.bpm.engine.ProcessEngine;
import org.camunda.bpm.engine.rest.security.auth.AuthenticationResult;
import org.camunda.bpm.engine.rest.security.auth.impl.HttpBasicAuthenticationProvider;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.servlet.http.HttpServletRequest;
import java.io.IOException;
import java.io.StringReader;
import java.security.*;
import java.security.spec.InvalidKeySpecException;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;


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
                    // Add the Bouncy Castle provider
                    Security.addProvider(new BouncyCastleProvider());

                    // Decode the PEM formatted public key
                    PemReader pemReader = new PemReader(new StringReader(publicKey));
                    PemObject pemObject = pemReader.readPemObject();
                    byte[] publicKeyBytes = pemObject.getContent();

                    // Create a public key instance from the decoded bytes
                    KeyFactory keyFactory = KeyFactory.getInstance("EdDSA", "BC");
                    X509EncodedKeySpec publicKeySpec = new X509EncodedKeySpec(publicKeyBytes);
                    PublicKey publicKey_ = keyFactory.generatePublic(publicKeySpec);

                    // Verify the JWT signature
                    Signature signature = Signature.getInstance("EdDSA", "BC");
                    signature.initVerify(publicKey_);
                    String[] parts = token.split("\\.");
                    if (parts.length < 3) {
                        return result;
                    }
                    signature.update(parts[0].concat(".").concat(parts[1]).getBytes());
                    byte[] jwtSignature = Base64.getUrlDecoder().decode(parts[2]);
                    boolean isSignatureValid = signature.verify(jwtSignature);

                    if (isSignatureValid) {
                        return AuthenticationResult.successful(token);
                    } else {
                        log.debug("JWT signature validation failed.");
                    }
                } catch (IOException | NoSuchAlgorithmException | NoSuchProviderException | InvalidKeySpecException |
                         SignatureException | InvalidKeyException e) {
                    // No op.
                }
            }
        }

        return result;
    }
}


package com.example.camunda;

import com.nimbusds.jwt.JWTClaimsSet;
import org.operaton.bpm.engine.impl.IdentityServiceImpl;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.text.ParseException;
import java.util.List;


public class JWTIdentityService extends IdentityServiceImpl {

    private static final Logger log = LoggerFactory.getLogger(JWTIdentityService.class);

    private String publicKey;

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
        // Persistent Basic Auth
        super.setAuthentication(userId, groups, tenantIds);
    }
}

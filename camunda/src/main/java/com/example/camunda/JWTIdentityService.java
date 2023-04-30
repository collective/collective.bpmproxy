package com.example.camunda;

import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.camunda.bpm.engine.impl.IdentityServiceImpl;
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
        try {
            // Transient JWT (verified at filter)
            SignedJWT jwt = SignedJWT.parse(userId);
            JWTClaimsSet claims = jwt.getJWTClaimsSet();
            userId = claims.getStringClaim("sub");
            groups = claims.getStringListClaim("groups");
            tenantIds = claims.getStringListClaim("tenant_ids");
            super.setAuthentication(userId, groups, tenantIds);
        } catch (NullPointerException | ParseException e) {
            // Persistent Basic Auth
            super.setAuthentication(userId, groups, tenantIds);
        }
    }
}

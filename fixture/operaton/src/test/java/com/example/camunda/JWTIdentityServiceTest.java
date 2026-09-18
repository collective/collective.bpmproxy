package com.example.camunda;

import org.bouncycastle.util.io.pem.PemObject;
import org.bouncycastle.util.io.pem.PemWriter;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.IOException;
import java.io.StringWriter;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PublicKey;
import java.security.Signature;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mockStatic;

import org.mockito.MockedStatic;

/**
 * These tests deliberately use real ed25519 keys and real signed tokens rather
 * than mocking {@code SignedJWT} statically: the point of the claims handling
 * is that it only trusts a token it has verified, and a static parse mock would
 * bypass exactly the code that has to be exercised.
 */
class JWTIdentityServiceTest {

    private JWTIdentityService service;
    private File tempFile;

    @BeforeEach
    void setUp() {
        service = new JWTIdentityService();
    }

    @AfterEach
    void tearDown() {
        if (tempFile != null && tempFile.exists()) {
            tempFile.delete();
        }
    }

    private KeyPair generateKeyPair() throws Exception {
        return KeyPairGenerator.getInstance("Ed25519").generateKeyPair();
    }

    private String toPem(PublicKey publicKey) throws Exception {
        StringWriter stringWriter = new StringWriter();
        try (PemWriter pemWriter = new PemWriter(stringWriter)) {
            pemWriter.writeObject(new PemObject("PUBLIC KEY", publicKey.getEncoded()));
        }
        return stringWriter.toString();
    }

    private String createToken(KeyPair keyPair, Instant expiration) throws Exception {
        String claims = "{\"sub\":\"testUser\","
                + "\"groups\":[\"group1\",\"group2\"],"
                + "\"tenant_ids\":[\"tenant1\"],"
                + "\"exp\":" + expiration.getEpochSecond() + "}";
        String header = Base64.getUrlEncoder().withoutPadding()
                .encodeToString("{\"alg\":\"EdDSA\"}".getBytes());
        String payload = Base64.getUrlEncoder().withoutPadding().encodeToString(claims.getBytes());
        String data = header + "." + payload;

        Signature sig = Signature.getInstance("Ed25519");
        sig.initSign(keyPair.getPrivate());
        sig.update(data.getBytes());
        return data + "." + Base64.getUrlEncoder().withoutPadding().encodeToString(sig.sign());
    }

    @Test
    void testGetPublicKeyFromFile() throws Exception {
        tempFile = File.createTempFile("pub", "key");
        Files.writeString(tempFile.toPath(), "test-public-key");
        service.setPublicKey(tempFile.getAbsolutePath());
        assertEquals("test-public-key", service.getPublicKey());
    }

    @Test
    void testGetPublicKeyFromFileIOException() throws Exception {
        tempFile = File.createTempFile("pub", "key");
        try (MockedStatic<Files> mockedFiles = mockStatic(Files.class)) {
            mockedFiles.when(() -> Files.readString(any(Path.class), any()))
                    .thenThrow(new IOException("test io exception"));
            service.setPublicKey(tempFile.getAbsolutePath());
            assertNull(service.getPublicKey());
        }
    }

    @Test
    void testGetPublicKeyFromString() {
        service.setPublicKey("direct-public-key-string");
        assertEquals("direct-public-key-string", service.getPublicKey());
    }

    @Test
    void testGetPublicKeyUnconfigured() {
        // Must not throw: the authentication filter calls this on every request.
        assertNull(service.getPublicKey());
    }

    @Test
    void testSetAuthenticationWithValidJWT() throws Exception {
        KeyPair keyPair = generateKeyPair();
        service.setPublicKey(toPem(keyPair.getPublic()));
        String token = createToken(keyPair, Instant.now().plusSeconds(3600));

        service.setAuthentication(token, null, null);

        var currentAuth = service.getCurrentAuthentication();
        assertEquals("testUser", currentAuth.getUserId());
        assertEquals(Arrays.asList("group1", "group2"), currentAuth.getGroupIds());
        assertEquals(List.of("tenant1"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationIgnoresClaimsOfExpiredJWT() throws Exception {
        KeyPair keyPair = generateKeyPair();
        service.setPublicKey(toPem(keyPair.getPublic()));
        String token = createToken(keyPair, Instant.now().minusSeconds(3600));

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        // The token's claims must not be adopted; the caller's values stand.
        var currentAuth = service.getCurrentAuthentication();
        assertEquals(token, currentAuth.getUserId());
        assertEquals(List.of("basic-group"), currentAuth.getGroupIds());
        assertEquals(List.of("basic-tenant"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationIgnoresClaimsOfWronglySignedJWT() throws Exception {
        KeyPair signing = generateKeyPair();
        KeyPair other = generateKeyPair();
        // Configure a key that did not sign this token.
        service.setPublicKey(toPem(other.getPublic()));
        String token = createToken(signing, Instant.now().plusSeconds(3600));

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        var currentAuth = service.getCurrentAuthentication();
        assertEquals(token, currentAuth.getUserId());
        assertEquals(List.of("basic-group"), currentAuth.getGroupIds());
        assertEquals(List.of("basic-tenant"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationWithInvalidJWT() {
        String invalidToken = "invalid";
        service.setPublicKey("not-a-pem");

        service.setAuthentication(invalidToken, List.of("group1"), List.of("tenant1"));

        var currentAuth = service.getCurrentAuthentication();
        assertEquals(invalidToken, currentAuth.getUserId());
        assertEquals(List.of("group1"), currentAuth.getGroupIds());
        assertEquals(List.of("tenant1"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationWithPlainUsername() {
        // Basic auth: no key configured, ordinary username.
        service.setAuthentication("user", List.of("group1"), List.of("tenant1"));

        var currentAuth = service.getCurrentAuthentication();
        assertEquals("user", currentAuth.getUserId());
        assertEquals(List.of("group1"), currentAuth.getGroupIds());
        assertEquals(List.of("tenant1"), currentAuth.getTenantIds());
    }
}

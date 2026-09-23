package com.example.camunda;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.JWSHeader;
import com.nimbusds.jose.crypto.RSASSASigner;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.RSAKey;
import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import com.sun.net.httpserver.HttpServer;
import org.bouncycastle.util.io.pem.PemObject;
import org.bouncycastle.util.io.pem.PemWriter;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.io.File;
import java.io.IOException;
import java.io.OutputStream;
import java.io.StringWriter;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PublicKey;
import java.security.Signature;
import java.security.interfaces.RSAPrivateKey;
import java.security.interfaces.RSAPublicKey;
import java.time.Instant;
import java.util.Arrays;
import java.util.Base64;
import java.util.Date;
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
    private HttpServer jwksServer;

    @BeforeEach
    void setUp() {
        service = new JWTIdentityService();
    }

    @AfterEach
    void tearDown() {
        if (tempFile != null && tempFile.exists()) {
            tempFile.delete();
        }
        if (jwksServer != null) {
            jwksServer.stop(0);
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

    private KeyPair generateRsaKeyPair() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("RSA");
        kpg.initialize(2048);
        return kpg.generateKeyPair();
    }

    /**
     * Starts a throwaway HTTP server serving a JWKS containing exactly the
     * given key, and returns the "issuer" URL for it -- the same value
     * {@link JWTIdentityService#setKeycloakIssuerUri} expects, since
     * {@code RemoteJWKSet} is configured to fetch
     * {@code <issuer>/protocol/openid-connect/certs}, matching Keycloak's
     * own layout.
     */
    private String startJwksServer(RSAPublicKey publicKey) throws Exception {
        RSAKey jwk = new RSAKey.Builder(publicKey).keyID("test-key").build();
        String jwksJson = new ObjectMapper().writeValueAsString(new JWKSet(jwk).toJSONObject());

        jwksServer = HttpServer.create(new InetSocketAddress("localhost", 0), 0);
        jwksServer.createContext("/protocol/openid-connect/certs", exchange -> {
            byte[] body = jwksJson.getBytes(StandardCharsets.UTF_8);
            exchange.getResponseHeaders().add("Content-Type", "application/json");
            exchange.sendResponseHeaders(200, body.length);
            try (OutputStream os = exchange.getResponseBody()) {
                os.write(body);
            }
        });
        jwksServer.start();
        return "http://localhost:" + jwksServer.getAddress().getPort();
    }

    private String createKeycloakToken(RSAPrivateKey privateKey, String issuer, Instant expiration,
                                        String usernameClaim, String usernameValue) throws Exception {
        return createKeycloakToken(privateKey, issuer, expiration, usernameClaim, usernameValue, null);
    }

    private String createKeycloakToken(RSAPrivateKey privateKey, String issuer, Instant expiration,
                                        String usernameClaim, String usernameValue,
                                        List<String> groups) throws Exception {
        JWTClaimsSet.Builder builder = new JWTClaimsSet.Builder()
                .issuer(issuer)
                .subject("service-account-operaton-worker")
                .expirationTime(Date.from(expiration));
        if (usernameClaim != null) {
            builder.claim(usernameClaim, usernameValue);
        }
        if (groups != null) {
            builder.claim("groups", groups);
        }
        SignedJWT jwt = new SignedJWT(new JWSHeader(JWSAlgorithm.RS256), builder.build());
        jwt.sign(new RSASSASigner(privateKey));
        return jwt.serialize();
    }

    @Test
    void testSetAuthenticationWithValidKeycloakJWT() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        // The realm's oidc-group-membership-mapper on the operaton-worker
        // client, the same mapper Cockpit's own OAuth2 login already uses.
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), issuer,
                Instant.now().plusSeconds(3600), "operaton_username", "admin", List.of("camunda-admin"));

        service.setAuthentication(token, null, null);

        // Resolves to a *persistent* engine user, the same way Basic Auth
        // would -- but with group membership taken from the token, the same
        // way Plone's JWT and Cockpit's own OAuth2 login already do.
        var currentAuth = service.getCurrentAuthentication();
        assertEquals("admin", currentAuth.getUserId());
        assertEquals(List.of("camunda-admin"), currentAuth.getGroupIds());
        assertNull(currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationKeycloakWithoutGroupsClaimFallsBackToPersistentGroups() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        // No groups claim at all: falls through to null, same as Basic Auth
        // passing no groups -- the engine resolves persistent membership.
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), issuer,
                Instant.now().plusSeconds(3600), "operaton_username", "admin");

        service.setAuthentication(token, null, null);

        assertNull(service.getCurrentAuthentication().getGroupIds());
    }

    @Test
    void testSetAuthenticationKeycloakFallsBackToPreferredUsername() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        // No hardcoded operaton_username claim: an interactive Cockpit login.
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), issuer,
                Instant.now().plusSeconds(3600), "preferred_username", "user");

        service.setAuthentication(token, null, null);

        assertEquals("user", service.getCurrentAuthentication().getUserId());
    }

    @Test
    void testSetAuthenticationIgnoresKeycloakJWTWhenOAuth2Disabled() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        // oauth2Enabled left false (default): Basic Auth is the configured
        // mode, so this otherwise-valid Keycloak token must not be adopted.
        service.setKeycloakIssuerUri(issuer);
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), issuer,
                Instant.now().plusSeconds(3600), "operaton_username", "admin");

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        var currentAuth = service.getCurrentAuthentication();
        assertEquals(token, currentAuth.getUserId());
        assertEquals(List.of("basic-group"), currentAuth.getGroupIds());
    }

    @Test
    void testSetAuthenticationIgnoresExpiredKeycloakJWT() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), issuer,
                Instant.now().minusSeconds(3600), "operaton_username", "admin");

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        assertEquals(token, service.getCurrentAuthentication().getUserId());
    }

    @Test
    void testSetAuthenticationIgnoresKeycloakJWTFromWrongIssuer() throws Exception {
        KeyPair keyPair = generateRsaKeyPair();
        String issuer = startJwksServer((RSAPublicKey) keyPair.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        // Signed by the right key, but claiming a different issuer.
        String token = createKeycloakToken((RSAPrivateKey) keyPair.getPrivate(), "http://attacker.example/realms/other",
                Instant.now().plusSeconds(3600), "operaton_username", "admin");

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        assertEquals(token, service.getCurrentAuthentication().getUserId());
    }

    @Test
    void testSetAuthenticationIgnoresWronglySignedKeycloakJWT() throws Exception {
        KeyPair signing = generateRsaKeyPair();
        KeyPair other = generateRsaKeyPair();
        // The JWKS endpoint advertises a different key than the one that
        // actually signed the token.
        String issuer = startJwksServer((RSAPublicKey) other.getPublic());
        service.setOAuth2Enabled(true);
        service.setKeycloakIssuerUri(issuer);
        String token = createKeycloakToken((RSAPrivateKey) signing.getPrivate(), issuer,
                Instant.now().plusSeconds(3600), "operaton_username", "admin");

        service.setAuthentication(token, List.of("basic-group"), List.of("basic-tenant"));

        assertEquals(token, service.getCurrentAuthentication().getUserId());
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

package com.example.camunda;

import org.bouncycastle.jce.provider.BouncyCastleProvider;
import org.bouncycastle.util.io.pem.PemObject;
import org.bouncycastle.util.io.pem.PemWriter;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.engine.ProcessEngine;
import org.operaton.bpm.engine.rest.security.auth.AuthenticationResult;

import jakarta.servlet.http.HttpServletRequest;

import java.io.StringWriter;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PublicKey;
import java.security.Security;
import java.security.Signature;
import java.time.Instant;
import java.util.Base64;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class JWTAuthenticationProviderTest {

    private JWTAuthenticationProvider provider;

    @Mock
    private HttpServletRequest request;

    @Mock
    private ProcessEngine engine;

    @Mock
    private JWTIdentityService identityService;

    @BeforeAll
    static void setupProvider() {
        Security.addProvider(new BouncyCastleProvider());
    }

    @BeforeEach
    void setUp() {
        provider = new JWTAuthenticationProvider();
    }

    private KeyPair generateKeyPair() throws Exception {
        KeyPairGenerator kpg = KeyPairGenerator.getInstance("Ed25519");
        return kpg.generateKeyPair();
    }

    private String getPublicKeyPem(PublicKey publicKey) throws Exception {
        StringWriter stringWriter = new StringWriter();
        PemWriter pemWriter = new PemWriter(stringWriter);
        pemWriter.writeObject(new PemObject("PUBLIC KEY", publicKey.getEncoded()));
        pemWriter.close();
        return stringWriter.toString();
    }

    private String createJwtToken(KeyPair keyPair) throws Exception {
        // Valid for an hour, like the tokens Plone mints.
        return createJwtToken(keyPair, "EdDSA", Instant.now().plusSeconds(3600));
    }

    private String createJwtToken(KeyPair keyPair, String alg, Instant expiration) throws Exception {
        String claims = expiration == null
                ? "{\"sub\":\"testUser\"}"
                : "{\"sub\":\"testUser\",\"exp\":" + expiration.getEpochSecond() + "}";
        String header = Base64.getUrlEncoder().withoutPadding()
                .encodeToString(("{\"alg\":\"" + alg + "\"}").getBytes());
        String payload = Base64.getUrlEncoder().withoutPadding().encodeToString(claims.getBytes());
        String data = header + "." + payload;

        Signature sig = Signature.getInstance("Ed25519");
        sig.initSign(keyPair.getPrivate());
        sig.update(data.getBytes());
        byte[] signatureBytes = sig.sign();

        String signature = Base64.getUrlEncoder().withoutPadding().encodeToString(signatureBytes);
        return data + "." + signature;
    }

    @Test
    void testExtractAuthenticatedUser_BasicAuthSuccess() {
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Basic dXNlcjpwYXNz");
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.checkPassword("user", "pass")).thenReturn(true);
        
        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertTrue(result.isAuthenticated());
        assertEquals("user", result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenSuccess() throws Exception {
        KeyPair keyPair = generateKeyPair();
        String token = createJwtToken(keyPair);
        
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(keyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertTrue(result.isAuthenticated());
        assertEquals(token, result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenInvalidSignature() throws Exception {
        KeyPair keyPair = generateKeyPair();
        KeyPair otherKeyPair = generateKeyPair();
        String token = createJwtToken(keyPair);
        
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(otherKeyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenInvalidParts() throws Exception {
        KeyPair keyPair = generateKeyPair();
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer invalid.token");
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(keyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_ExceptionInvalidPem() throws Exception {
        String invalidKeyPem = "-----BEGIN PUBLIC KEY-----\ninvalidbase64content\n-----END PUBLIC KEY-----";
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer a.b.c");
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(invalidKeyPem);

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_NoBearerPrefix() {
        // No stubbing of the identity service: the provider must bail out on
        // the header alone, without consulting the engine.
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("InvalidPrefix something");

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_NullHeader() {
        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn(null);

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);
        
        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenExpired() throws Exception {
        KeyPair keyPair = generateKeyPair();
        // Correctly signed, but expired well beyond the clock-skew allowance.
        String token = createJwtToken(keyPair, "EdDSA", Instant.now().minusSeconds(3600));

        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(keyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);

        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenWithoutExpiry() throws Exception {
        KeyPair keyPair = generateKeyPair();
        // Fail closed: Plone always sets exp, so a token without one is not
        // from a supported client.
        String token = createJwtToken(keyPair, "EdDSA", null);

        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(keyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);

        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_JwtTokenUnexpectedAlgorithm() throws Exception {
        KeyPair keyPair = generateKeyPair();
        // Signed with the right key, but claiming a different algorithm.
        String token = createJwtToken(keyPair, "HS256", Instant.now().plusSeconds(3600));

        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(getPublicKeyPem(keyPair.getPublic()));

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);

        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }

    @Test
    void testExtractAuthenticatedUser_NoPublicKeyConfigured() throws Exception {
        KeyPair keyPair = generateKeyPair();
        String token = createJwtToken(keyPair);

        when(request.getHeader(org.springframework.http.HttpHeaders.AUTHORIZATION)).thenReturn("Bearer " + token);
        when(engine.getIdentityService()).thenReturn(identityService);
        when(identityService.getPublicKey()).thenReturn(null);

        AuthenticationResult result = provider.extractAuthenticatedUser(request, engine);

        assertFalse(result.isAuthenticated());
        assertNull(result.getAuthenticatedUser());
    }
}

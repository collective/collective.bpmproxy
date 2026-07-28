package com.example.camunda;

import com.nimbusds.jwt.JWTClaimsSet;
import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.MockedStatic;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.ParseException;
import java.util.Arrays;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class JWTIdentityServiceTest {

    private JWTIdentityService service;
    private MockedStatic<SignedJWT> mockedSignedJWT;
    private File tempFile;

    @BeforeEach
    void setUp() {
        service = new JWTIdentityService();
        mockedSignedJWT = mockStatic(SignedJWT.class);
    }

    @AfterEach
    void tearDown() {
        mockedSignedJWT.close();
        if (tempFile != null && tempFile.exists()) {
            tempFile.delete();
        }
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
            mockedFiles.when(() -> Files.readString(any(Path.class), any())).thenThrow(new IOException("test io exception"));
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
    void testSetAuthenticationWithValidJWT() throws ParseException {
        String token = "dummy.jwt.token";
        SignedJWT jwtMock = mock(SignedJWT.class);
        JWTClaimsSet claimsMock = mock(JWTClaimsSet.class);

        mockedSignedJWT.when(() -> SignedJWT.parse(token)).thenReturn(jwtMock);
        when(jwtMock.getJWTClaimsSet()).thenReturn(claimsMock);

        when(claimsMock.getStringClaim("sub")).thenReturn("testUser");
        when(claimsMock.getStringListClaim("groups")).thenReturn(Arrays.asList("group1", "group2"));
        when(claimsMock.getStringListClaim("tenant_ids")).thenReturn(Arrays.asList("tenant1"));

        service.setAuthentication(token, null, null);

        org.operaton.bpm.engine.impl.identity.Authentication currentAuth = service.getCurrentAuthentication();
        assertEquals("testUser", currentAuth.getUserId());
        assertEquals(Arrays.asList("group1", "group2"), currentAuth.getGroupIds());
        assertEquals(Arrays.asList("tenant1"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationWithInvalidJWT() throws ParseException {
        String invalidToken = "invalid";
        mockedSignedJWT.when(() -> SignedJWT.parse(invalidToken)).thenThrow(new ParseException("error", 0));

        service.setAuthentication(invalidToken, Arrays.asList("group1"), Arrays.asList("tenant1"));

        org.operaton.bpm.engine.impl.identity.Authentication currentAuth = service.getCurrentAuthentication();
        assertEquals(invalidToken, currentAuth.getUserId());
        assertEquals(Arrays.asList("group1"), currentAuth.getGroupIds());
        assertEquals(Arrays.asList("tenant1"), currentAuth.getTenantIds());
    }

    @Test
    void testSetAuthenticationWithNullJWT() {
        mockedSignedJWT.when(() -> SignedJWT.parse(anyString())).thenThrow(new NullPointerException());

        service.setAuthentication("user", Arrays.asList("group1"), Arrays.asList("tenant1"));

        org.operaton.bpm.engine.impl.identity.Authentication currentAuth = service.getCurrentAuthentication();
        assertEquals("user", currentAuth.getUserId());
        assertEquals(Arrays.asList("group1"), currentAuth.getGroupIds());
        assertEquals(Arrays.asList("tenant1"), currentAuth.getTenantIds());
    }
}

package com.example.camunda;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.engine.ProcessEngine;
import org.operaton.bpm.engine.impl.bpmn.parser.BpmnParseListener;
import org.operaton.bpm.engine.impl.cfg.ProcessEngineConfigurationImpl;
import org.operaton.bpm.engine.impl.cfg.ProcessEnginePlugin;
import org.operaton.bpm.engine.impl.plugin.AdministratorAuthorizationPlugin;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.operaton.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class ProcessEngineConfigTest {

    @Mock
    private ProcessEngineConfigurationImpl processEngineConfiguration;

    @Mock
    private ProcessEngine processEngine;

    @Test
    void testCustomProcessEnginePlugin_PreInit_NullListeners() {
        ProcessEngineConfig config = new ProcessEngineConfig();
        ReflectionTestUtils.setField(config, "jwtPublicKey", "dummy-key");
        
        ProcessEnginePlugin plugin = config.customProcessEnginePlugin();
        
        when(processEngineConfiguration.getCustomPostBPMNParseListeners()).thenReturn(null);
        
        plugin.preInit(processEngineConfiguration);
        
        verify(processEngineConfiguration).setCustomPostBPMNParseListeners(argThat(list -> 
            list != null && list.size() == 1 && list.get(0) instanceof EngineBpmnParseListener
        ));
        
        verify(processEngineConfiguration).setIdentityService(argThat(service -> 
            service instanceof JWTIdentityService
        ));
    }

    @Test
    void testCustomProcessEnginePlugin_PreInit_ExistingListeners() {
        ProcessEngineConfig config = new ProcessEngineConfig();
        ReflectionTestUtils.setField(config, "jwtPublicKey", "dummy-key");
        
        ProcessEnginePlugin plugin = config.customProcessEnginePlugin();
        
        List<BpmnParseListener> existingListeners = new ArrayList<>();
        when(processEngineConfiguration.getCustomPostBPMNParseListeners()).thenReturn(existingListeners);
        
        plugin.preInit(processEngineConfiguration);
        
        verify(processEngineConfiguration).setCustomPostBPMNParseListeners(argThat(list -> 
            list != null && list.size() == 1 && list.get(0) instanceof EngineBpmnParseListener
        ));
    }

    @Test
    void testCustomProcessEnginePlugin_PostInitAndPostProcessEngineBuild() {
        ProcessEngineConfig config = new ProcessEngineConfig();
        ProcessEnginePlugin plugin = config.customProcessEnginePlugin();
        
        assertDoesNotThrow(() -> plugin.postInit(processEngineConfiguration));
        assertDoesNotThrow(() -> plugin.postProcessEngineBuild(processEngine));
    }

    @Test
    void testAdministratorAuthorizationPlugin() {
        ProcessEngineConfig config = new ProcessEngineConfig();
        ProcessEnginePlugin plugin = config.administratorAuthorizationPlugin();
        
        assertTrue(plugin instanceof AdministratorAuthorizationPlugin);
        AdministratorAuthorizationPlugin adminPlugin = (AdministratorAuthorizationPlugin) plugin;
        assertEquals("camunda-admin", adminPlugin.getAdministratorGroupName());
    }

    @Test
    void testAuthenticationFilter() {
        ProcessEngineConfig config = new ProcessEngineConfig();
        FilterRegistrationBean<ProcessEngineAuthenticationFilter> registration = config.authenticationFilter();
        
        assertNotNull(registration);
        assertTrue(registration.getFilter() instanceof ProcessEngineAuthenticationFilter);
        assertEquals("com.example.camunda.JWTAuthenticationProvider", registration.getInitParameters().get("authentication-provider"));
        assertTrue(registration.getUrlPatterns().contains("/engine-rest/*"));
    }
}

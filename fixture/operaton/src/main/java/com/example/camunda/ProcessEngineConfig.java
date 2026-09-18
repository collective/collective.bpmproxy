package com.example.camunda;

import org.operaton.bpm.engine.impl.cfg.ProcessEngineConfigurationImpl;
import org.operaton.bpm.engine.impl.cfg.ProcessEnginePlugin;
import org.operaton.bpm.engine.impl.bpmn.parser.BpmnParseListener;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.ArrayList;
import java.util.List;

@Configuration
public class ProcessEngineConfig {

    @Value("${plone.public-key:ec-ed25519-pub-key.pem}")
    private String jwtPublicKey;

    @Bean
    public ProcessEnginePlugin customProcessEnginePlugin() {
        return new ProcessEnginePlugin() {
            @Override
            public void preInit(ProcessEngineConfigurationImpl processEngineConfiguration) {
                // Configure business rule tasks / DMN to always require result
                List<BpmnParseListener> postBpmnParseListeners = processEngineConfiguration.getCustomPostBPMNParseListeners();
                if (postBpmnParseListeners == null) {
                    postBpmnParseListeners = new ArrayList<>();
                }
                postBpmnParseListeners.add(new EngineBpmnParseListener());
                processEngineConfiguration.setCustomPostBPMNParseListeners(postBpmnParseListeners);

                // Configure JWT authentication
                JWTIdentityService identityService = new JWTIdentityService();
                identityService.setPublicKey(jwtPublicKey);
                processEngineConfiguration.setIdentityService(identityService);
            }

            @Override
            public void postInit(ProcessEngineConfigurationImpl processEngineConfiguration) {
            }

            @Override
            public void postProcessEngineBuild(org.operaton.bpm.engine.ProcessEngine processEngine) {
            }
        };
    }

    @Bean
    public ProcessEnginePlugin administratorAuthorizationPlugin() {
        // Plone signs JWTs with group "camunda-admin" (CAMUNDA_ADMIN_GROUP) and
        // the Keycloak realm carries the same group; grant it engine-wide admin
        // instead of Operaton's default "operaton-admin".
        org.operaton.bpm.engine.impl.plugin.AdministratorAuthorizationPlugin plugin =
            new org.operaton.bpm.engine.impl.plugin.AdministratorAuthorizationPlugin();
        plugin.setAdministratorGroupName("camunda-admin");
        return plugin;
    }

    @Bean
    public org.springframework.boot.web.servlet.FilterRegistrationBean<org.operaton.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter> authenticationFilter() {
        org.springframework.boot.web.servlet.FilterRegistrationBean<org.operaton.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter> registration = new org.springframework.boot.web.servlet.FilterRegistrationBean<>();
        org.operaton.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter filter = new org.operaton.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter();
        registration.setFilter(filter);
        registration.addInitParameter("authentication-provider", "com.example.camunda.JWTAuthenticationProvider");
        registration.addUrlPatterns("/engine-rest/*");
        return registration;
    }
}

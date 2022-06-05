package com.example.camunda;

import info.novatec.micronaut.camunda.bpm.feature.MnProcessEngineConfiguration;
import info.novatec.micronaut.camunda.bpm.feature.ProcessEngineConfigurationCustomizer;
import io.micronaut.context.annotation.Replaces;
import io.micronaut.context.annotation.Value;
import jakarta.inject.Singleton;
import org.camunda.bpm.engine.impl.bpmn.parser.BpmnParseListener;
import org.camunda.connect.plugin.impl.ConnectProcessEnginePlugin;
import org.camunda.spin.plugin.impl.SpinProcessEnginePlugin;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayList;
import java.util.List;

@Singleton
@Replaces(ProcessEngineConfigurationCustomizer.class)
public class Configuration implements ProcessEngineConfigurationCustomizer {

    private static final Logger log = LoggerFactory.getLogger(Configuration.class);

    @Value("${plone.publicKey:ec-prime256v1-pub-key.pem}")
    private String jwtPublicKey;

    @Override
    public void customize(MnProcessEngineConfiguration processEngineConfiguration) {
        // Configure Spin JSON support
        processEngineConfiguration.getProcessEnginePlugins().add(new SpinProcessEnginePlugin());
        processEngineConfiguration.getProcessEnginePlugins().add(new ConnectProcessEnginePlugin());
        processEngineConfiguration.setDefaultSerializationFormat("application/json");

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

        // Allow to work around issue where server startup fails on empty db
        // Map<String, String> env = System.getenv();
        // if (env.get("NRestarts") == null || env.get("NRestarts").equals("0")) {
        //     processEngineConfiguration.setHistoryCleanupBatchWindowStartTime("22:00");
        //     log.info("History cleanup batch window start time set to 22:00.");
        // } else {
        //     log.info("History cleanup batch window start time NOT set.");
        // }
    }
}

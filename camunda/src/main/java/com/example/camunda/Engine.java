package com.example.camunda;

import info.novatec.micronaut.camunda.bpm.feature.CamundaVersion;
import info.novatec.micronaut.camunda.bpm.feature.ProcessEngineFactory;
import info.novatec.micronaut.camunda.bpm.feature.initialization.ParallelInitializationService;
import io.micronaut.context.annotation.Replaces;
import io.micronaut.jdbc.BasicJdbcConfiguration;
import io.micronaut.transaction.SynchronousTransactionManager;
import jakarta.inject.Singleton;
import org.camunda.bpm.engine.*;
import org.camunda.bpm.engine.impl.persistence.entity.AuthorizationEntity;
import org.camunda.bpm.engine.migration.MigrationInstructionsBuilder;
import org.camunda.bpm.engine.migration.MigrationPlan;
import org.camunda.bpm.engine.migration.MigrationPlanExecutionBuilder;
import org.camunda.bpm.engine.repository.ProcessDefinition;
import org.camunda.bpm.engine.repository.ProcessDefinitionQuery;
import org.camunda.bpm.engine.runtime.ProcessInstance;
import org.camunda.bpm.engine.runtime.ProcessInstanceQuery;
import org.jetbrains.annotations.NotNull;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.sql.Connection;
import java.util.ArrayList;
import java.util.List;

import static org.camunda.bpm.engine.authorization.Authorization.ANY;
import static org.camunda.bpm.engine.authorization.Authorization.AUTH_TYPE_GLOBAL;
import static org.camunda.bpm.engine.authorization.Permissions.CREATE_INSTANCE;
import static org.camunda.bpm.engine.authorization.Permissions.READ;
import static org.camunda.bpm.engine.authorization.Permissions.CREATE;
import static org.camunda.bpm.engine.authorization.Resources.PROCESS_DEFINITION;
import static org.camunda.bpm.engine.authorization.Resources.PROCESS_INSTANCE;

@Singleton
@Replaces(ProcessEngineFactory.class)
public class Engine extends ProcessEngineFactory {

    private static final Logger log = LoggerFactory.getLogger(Engine.class);

    @Override
    public ProcessEngine processEngine(ProcessEngineConfiguration processEngineConfiguration, CamundaVersion camundaVersion, SynchronousTransactionManager<Connection> transactionManager, BasicJdbcConfiguration basicJdbcConfiguration, ParallelInitializationService parallelInitializationService) {
        ProcessEngine processEngine = super.processEngine(processEngineConfiguration, camundaVersion, transactionManager, basicJdbcConfiguration, parallelInitializationService);
        try {
            migrateProcessInstances(processEngine.getRepositoryService(), processEngine.getRuntimeService());
        } catch (IOException e) {
            log.warn(e.toString());
        }
        defaultAuthorizations(processEngine.getAuthorizationService());
        return processEngine;
    }

    protected void defaultAuthorizations(AuthorizationService authorizationService) {
        // Allow authorized users to read process definitions (for BPMN XML)
        if (authorizationService
                .createAuthorizationQuery()
                .authorizationType(AUTH_TYPE_GLOBAL)
                .resourceType(PROCESS_DEFINITION)
                .resourceId(ANY).count() == 0) {
            AuthorizationEntity usersAuth = new AuthorizationEntity(AUTH_TYPE_GLOBAL);
            usersAuth.setResource(PROCESS_DEFINITION);
            usersAuth.addPermission(READ);
            usersAuth.addPermission(CREATE_INSTANCE);
            usersAuth.setResourceId(ANY);
            authorizationService.saveAuthorization(usersAuth);
        }
        // Allow authorized users to create new process instances
        if (authorizationService
                .createAuthorizationQuery()
                .authorizationType(AUTH_TYPE_GLOBAL)
                .resourceType(PROCESS_INSTANCE)
                .resourceId(ANY).count() == 0) {
            AuthorizationEntity usersAuth = new AuthorizationEntity(AUTH_TYPE_GLOBAL);
            usersAuth.setResource(PROCESS_INSTANCE);
            usersAuth.addPermission(CREATE);
            usersAuth.setResourceId(ANY);
            authorizationService.saveAuthorization(usersAuth);
        }
    }

    protected void migrateProcessInstances(RepositoryService repositoryService, RuntimeService runtimeService) throws IOException {
        ProcessDefinitionQuery processDefinitionQuery = repositoryService.createProcessDefinitionQuery();
        List<ProcessDefinition> processDefinitionList = processDefinitionQuery.latestVersion().list();

        for (ProcessDefinition processDefinition: processDefinitionList) {

            ProcessInstanceQuery processInstanceQuery = runtimeService.createProcessInstanceQuery();
            List<ProcessInstance> processInstanceList = processInstanceQuery.processDefinitionKey(processDefinition.getKey()).list();

            for (ProcessInstance processInstance: processInstanceList) {

                String processDefinitionId = processInstance.getProcessDefinitionId();
                ProcessDefinition localProcessDefinition = repositoryService.createProcessDefinitionQuery().processDefinitionId(processDefinitionId).singleResult();

                if (localProcessDefinition.getVersion() < processDefinition.getVersion()) {

                    List<String> processInstanceIds = new ArrayList<>();
                    processInstanceIds.add(processInstance.getId());
                    MigrationInstructionsBuilder instructionsBuilder = runtimeService.createMigrationPlan(localProcessDefinition.getId(), processDefinition.getId()).mapEqualActivities();
                    MigrationPlan migrationPlan = instructionsBuilder.updateEventTriggers().build();
                    MigrationPlanExecutionBuilder executionBuilder = runtimeService.newMigration(migrationPlan).processInstanceIds(processInstanceIds);

                    try {
                        executionBuilder.execute();
                    } catch(Exception e) {
                        log.warn(e.toString());
                    }
                }
            }
        }
    }
}

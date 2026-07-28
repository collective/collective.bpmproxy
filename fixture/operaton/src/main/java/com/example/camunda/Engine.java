package com.example.camunda;

import org.operaton.bpm.engine.*;
import org.operaton.bpm.engine.impl.persistence.entity.AuthorizationEntity;
import org.operaton.bpm.engine.migration.MigrationInstructionsBuilder;
import org.operaton.bpm.engine.migration.MigrationPlan;
import org.operaton.bpm.engine.migration.MigrationPlanExecutionBuilder;
import org.operaton.bpm.engine.repository.ProcessDefinition;
import org.operaton.bpm.engine.repository.ProcessDefinitionQuery;
import org.operaton.bpm.engine.runtime.ProcessInstance;
import org.operaton.bpm.engine.runtime.ProcessInstanceQuery;
import org.operaton.bpm.spring.boot.starter.event.PostDeployEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Component;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.ArrayList;
import java.util.List;

import static org.operaton.bpm.engine.authorization.Authorization.ANY;
import static org.operaton.bpm.engine.authorization.Authorization.AUTH_TYPE_GLOBAL;
import static org.operaton.bpm.engine.authorization.Permissions.CREATE_INSTANCE;
import static org.operaton.bpm.engine.authorization.Permissions.READ;
import static org.operaton.bpm.engine.authorization.Permissions.CREATE;
import static org.operaton.bpm.engine.authorization.Resources.PROCESS_DEFINITION;
import static org.operaton.bpm.engine.authorization.Resources.PROCESS_INSTANCE;

@Component
public class Engine {

    private static final Logger log = LoggerFactory.getLogger(Engine.class);

    @EventListener
    public void onPostDeploy(PostDeployEvent event) {
        ProcessEngine processEngine = event.getProcessEngine();
        try {
            migrateProcessInstances(processEngine.getRepositoryService(), processEngine.getRuntimeService());
        } catch (IOException e) {
            log.warn(e.toString());
        }
        defaultAuthorizations(processEngine.getAuthorizationService());
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

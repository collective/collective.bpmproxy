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

    /**
     * Grants every authenticated principal READ + CREATE_INSTANCE on every
     * process definition, and CREATE on every process instance -- global,
     * not scoped to camunda-admin or any other group.
     *
     * This was investigated as a possible over-permissive default (a review
     * finding: "any authenticated principal can start any process") and is
     * being kept deliberately, not left unnoticed:
     *
     *   - Real access control here is Plone's, not the engine's. Every
     *     request the engine sees was signed by collective.bpmproxy's own
     *     JWTAuthenticationProvider (see that class), which only accepts
     *     tokens Plone itself minted -- so "any authenticated principal"
     *     means "reached a Plone view that decided to call the engine",
     *     already gated by that view's own Plone permission (View/Add on the
     *     Bpm Proxy content object, including the anonymous-visitor case
     *     documented in docs/user/10-anonymous-and-tenancy.md).
     *   - The anonymous requester flow depends on this: an anonymous
     *     visitor's minted identity (client.py's get_authorization(),
     *     "anonymous-<uuid>") carries an empty groups claim by design --
     *     there is no Plone group to scope a narrower grant to. Restricting
     *     PROCESS_DEFINITION/PROCESS_INSTANCE to a named group would have to
     *     either exclude anonymous visitors (breaking the contact-form
     *     scenario) or introduce a new per-process-to-Plone-group mapping
     *     this add-on does not otherwise have.
     *   - operaton.bpm.authorization.enabled=true still does real work: it
     *     is what keeps deployment and admin-management resources
     *     (Authorization/User/Group) row-level filtered by group, and it is
     *     what makes camunda-admin-only actions like deployment actually
     *     admin-only (see EngineTest, JWTIdentityServiceTest).
     *
     * If you are tightening this, anonymous visitor interactions (such as an
     * anonymous user submitting a contact form with no named-user account)
     * are what breaks first -- test the anonymous flow end to end after any
     * change here.
     */
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

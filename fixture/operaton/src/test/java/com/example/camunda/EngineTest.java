package com.example.camunda;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.engine.AuthorizationService;
import org.operaton.bpm.engine.ProcessEngine;
import org.operaton.bpm.engine.RepositoryService;
import org.operaton.bpm.engine.RuntimeService;
import org.operaton.bpm.engine.authorization.AuthorizationQuery;
import org.operaton.bpm.engine.impl.persistence.entity.AuthorizationEntity;
import org.operaton.bpm.engine.migration.MigrationInstructionsBuilder;
import org.operaton.bpm.engine.migration.MigrationPlan;
import org.operaton.bpm.engine.migration.MigrationPlanExecutionBuilder;
import org.operaton.bpm.engine.repository.ProcessDefinition;
import org.operaton.bpm.engine.repository.ProcessDefinitionQuery;
import org.operaton.bpm.engine.runtime.ProcessInstance;
import org.operaton.bpm.engine.runtime.ProcessInstanceQuery;
import org.operaton.bpm.spring.boot.starter.event.PostDeployEvent;

import java.io.IOException;
import java.util.Collections;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;
import static org.operaton.bpm.engine.authorization.Authorization.ANY;
import static org.operaton.bpm.engine.authorization.Authorization.AUTH_TYPE_GLOBAL;
import static org.operaton.bpm.engine.authorization.Permissions.CREATE;
import static org.operaton.bpm.engine.authorization.Permissions.CREATE_INSTANCE;
import static org.operaton.bpm.engine.authorization.Permissions.READ;
import static org.operaton.bpm.engine.authorization.Resources.PROCESS_DEFINITION;
import static org.operaton.bpm.engine.authorization.Resources.PROCESS_INSTANCE;

@ExtendWith(MockitoExtension.class)
public class EngineTest {

    @Mock
    private ProcessEngine processEngine;
    
    @Mock
    private RepositoryService repositoryService;
    
    @Mock
    private RuntimeService runtimeService;
    
    @Mock
    private AuthorizationService authorizationService;

    @Mock
    private PostDeployEvent postDeployEvent;

    @Test
    void testOnPostDeploy() throws IOException {
        Engine engine = spy(new Engine());
        when(postDeployEvent.getProcessEngine()).thenReturn(processEngine);
        when(processEngine.getRepositoryService()).thenReturn(repositoryService);
        when(processEngine.getRuntimeService()).thenReturn(runtimeService);
        when(processEngine.getAuthorizationService()).thenReturn(authorizationService);
        
        doNothing().when(engine).migrateProcessInstances(repositoryService, runtimeService);
        doNothing().when(engine).defaultAuthorizations(authorizationService);
        
        engine.onPostDeploy(postDeployEvent);
        
        verify(engine).migrateProcessInstances(repositoryService, runtimeService);
        verify(engine).defaultAuthorizations(authorizationService);
    }
    
    @Test
    void testOnPostDeploy_MigrationThrowsIOException() throws IOException {
        Engine engine = spy(new Engine());
        when(postDeployEvent.getProcessEngine()).thenReturn(processEngine);
        when(processEngine.getRepositoryService()).thenReturn(repositoryService);
        when(processEngine.getRuntimeService()).thenReturn(runtimeService);
        when(processEngine.getAuthorizationService()).thenReturn(authorizationService);
        
        doThrow(new IOException("test io exception")).when(engine).migrateProcessInstances(repositoryService, runtimeService);
        doNothing().when(engine).defaultAuthorizations(authorizationService);
        
        engine.onPostDeploy(postDeployEvent);
        
        verify(engine).migrateProcessInstances(repositoryService, runtimeService);
        verify(engine).defaultAuthorizations(authorizationService);
    }

    @Test
    void testDefaultAuthorizations_CreatesAuthorizations() {
        Engine engine = new Engine();
        
        AuthorizationQuery authQueryDef = mock(AuthorizationQuery.class);
        when(authorizationService.createAuthorizationQuery()).thenReturn(authQueryDef);
        
        when(authQueryDef.authorizationType(AUTH_TYPE_GLOBAL)).thenReturn(authQueryDef);
        when(authQueryDef.resourceType(any())).thenReturn(authQueryDef);
        when(authQueryDef.resourceId(ANY)).thenReturn(authQueryDef);
        when(authQueryDef.count()).thenReturn(0L);
        
        engine.defaultAuthorizations(authorizationService);
        
        verify(authorizationService, times(2)).saveAuthorization(any(AuthorizationEntity.class));
    }
    
    @Test
    void testDefaultAuthorizations_AlreadyExists() {
        Engine engine = new Engine();
        
        AuthorizationQuery authQueryDef = mock(AuthorizationQuery.class);
        when(authorizationService.createAuthorizationQuery()).thenReturn(authQueryDef);
        
        when(authQueryDef.authorizationType(AUTH_TYPE_GLOBAL)).thenReturn(authQueryDef);
        when(authQueryDef.resourceType(any())).thenReturn(authQueryDef);
        when(authQueryDef.resourceId(ANY)).thenReturn(authQueryDef);
        when(authQueryDef.count()).thenReturn(1L);
        
        engine.defaultAuthorizations(authorizationService);
        
        verify(authorizationService, never()).saveAuthorization(any(AuthorizationEntity.class));
    }

    @Test
    void testMigrateProcessInstances_MigrationNeeded() throws IOException {
        Engine engine = new Engine();
        
        ProcessDefinitionQuery processDefinitionQuery = mock(ProcessDefinitionQuery.class);
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery);
        when(processDefinitionQuery.latestVersion()).thenReturn(processDefinitionQuery);
        
        ProcessDefinition latestDef = mock(ProcessDefinition.class);
        when(latestDef.getKey()).thenReturn("my-process");
        when(latestDef.getVersion()).thenReturn(2);
        when(latestDef.getId()).thenReturn("def-2");
        when(processDefinitionQuery.list()).thenReturn(Collections.singletonList(latestDef));
        
        ProcessInstanceQuery processInstanceQuery = mock(ProcessInstanceQuery.class);
        when(runtimeService.createProcessInstanceQuery()).thenReturn(processInstanceQuery);
        when(processInstanceQuery.processDefinitionKey("my-process")).thenReturn(processInstanceQuery);
        
        ProcessInstance instance = mock(ProcessInstance.class);
        when(instance.getProcessDefinitionId()).thenReturn("def-1");
        when(instance.getId()).thenReturn("inst-1");
        when(processInstanceQuery.list()).thenReturn(Collections.singletonList(instance));
        
        ProcessDefinitionQuery singleDefQuery = mock(ProcessDefinitionQuery.class);
        // Important: use doReturn for builder methods that we can't easily distinguish if called twice with same mocks
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery, singleDefQuery);
        
        // Wait, repositoryService.createProcessDefinitionQuery() is called twice!
        // First time: returns processDefinitionQuery. Second time: returns singleDefQuery.
        // Let's use thenReturn(processDefinitionQuery, singleDefQuery);
        
        when(singleDefQuery.processDefinitionId("def-1")).thenReturn(singleDefQuery);
        
        ProcessDefinition localDef = mock(ProcessDefinition.class);
        when(localDef.getVersion()).thenReturn(1);
        when(localDef.getId()).thenReturn("def-1");
        when(singleDefQuery.singleResult()).thenReturn(localDef);
        
        MigrationInstructionsBuilder instrBuilder = mock(MigrationInstructionsBuilder.class);
        when(runtimeService.createMigrationPlan("def-1", "def-2")).thenReturn(instrBuilder);
        when(instrBuilder.mapEqualActivities()).thenReturn(instrBuilder);
        when(instrBuilder.updateEventTriggers()).thenReturn(instrBuilder);
        
        MigrationPlan plan = mock(MigrationPlan.class);
        when(instrBuilder.build()).thenReturn(plan);
        
        MigrationPlanExecutionBuilder execBuilder = mock(MigrationPlanExecutionBuilder.class);
        when(runtimeService.newMigration(plan)).thenReturn(execBuilder);
        when(execBuilder.processInstanceIds(Collections.singletonList("inst-1"))).thenReturn(execBuilder);
        
        engine.migrateProcessInstances(repositoryService, runtimeService);
        
        verify(execBuilder).execute();
    }

    @Test
    void testMigrateProcessInstances_NoMigrationNeeded() throws IOException {
        Engine engine = new Engine();
        
        ProcessDefinitionQuery processDefinitionQuery = mock(ProcessDefinitionQuery.class);
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery);
        when(processDefinitionQuery.latestVersion()).thenReturn(processDefinitionQuery);
        
        ProcessDefinition latestDef = mock(ProcessDefinition.class);
        when(latestDef.getKey()).thenReturn("my-process");
        when(latestDef.getVersion()).thenReturn(2);
        when(processDefinitionQuery.list()).thenReturn(Collections.singletonList(latestDef));
        
        ProcessInstanceQuery processInstanceQuery = mock(ProcessInstanceQuery.class);
        when(runtimeService.createProcessInstanceQuery()).thenReturn(processInstanceQuery);
        when(processInstanceQuery.processDefinitionKey("my-process")).thenReturn(processInstanceQuery);
        
        ProcessInstance instance = mock(ProcessInstance.class);
        when(instance.getProcessDefinitionId()).thenReturn("def-2");
        when(processInstanceQuery.list()).thenReturn(Collections.singletonList(instance));
        
        ProcessDefinitionQuery singleDefQuery = mock(ProcessDefinitionQuery.class);
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery, singleDefQuery);
        
        when(singleDefQuery.processDefinitionId("def-2")).thenReturn(singleDefQuery);
        
        ProcessDefinition localDef = mock(ProcessDefinition.class);
        when(localDef.getVersion()).thenReturn(2); // same version
        when(singleDefQuery.singleResult()).thenReturn(localDef);
        
        engine.migrateProcessInstances(repositoryService, runtimeService);
        
        verify(runtimeService, never()).createMigrationPlan(anyString(), anyString());
    }

    @Test
    void testMigrateProcessInstances_ExecutionException() throws IOException {
        Engine engine = new Engine();
        
        ProcessDefinitionQuery processDefinitionQuery = mock(ProcessDefinitionQuery.class);
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery);
        when(processDefinitionQuery.latestVersion()).thenReturn(processDefinitionQuery);
        
        ProcessDefinition latestDef = mock(ProcessDefinition.class);
        when(latestDef.getKey()).thenReturn("my-process");
        when(latestDef.getVersion()).thenReturn(2);
        when(latestDef.getId()).thenReturn("def-2");
        when(processDefinitionQuery.list()).thenReturn(Collections.singletonList(latestDef));
        
        ProcessInstanceQuery processInstanceQuery = mock(ProcessInstanceQuery.class);
        when(runtimeService.createProcessInstanceQuery()).thenReturn(processInstanceQuery);
        when(processInstanceQuery.processDefinitionKey("my-process")).thenReturn(processInstanceQuery);
        
        ProcessInstance instance = mock(ProcessInstance.class);
        when(instance.getProcessDefinitionId()).thenReturn("def-1");
        when(instance.getId()).thenReturn("inst-1");
        when(processInstanceQuery.list()).thenReturn(Collections.singletonList(instance));
        
        ProcessDefinitionQuery singleDefQuery = mock(ProcessDefinitionQuery.class);
        when(repositoryService.createProcessDefinitionQuery()).thenReturn(processDefinitionQuery, singleDefQuery);
        
        when(singleDefQuery.processDefinitionId("def-1")).thenReturn(singleDefQuery);
        
        ProcessDefinition localDef = mock(ProcessDefinition.class);
        when(localDef.getVersion()).thenReturn(1);
        when(localDef.getId()).thenReturn("def-1");
        when(singleDefQuery.singleResult()).thenReturn(localDef);
        
        MigrationInstructionsBuilder instrBuilder = mock(MigrationInstructionsBuilder.class);
        when(runtimeService.createMigrationPlan("def-1", "def-2")).thenReturn(instrBuilder);
        when(instrBuilder.mapEqualActivities()).thenReturn(instrBuilder);
        when(instrBuilder.updateEventTriggers()).thenReturn(instrBuilder);
        
        MigrationPlan plan = mock(MigrationPlan.class);
        when(instrBuilder.build()).thenReturn(plan);
        
        MigrationPlanExecutionBuilder execBuilder = mock(MigrationPlanExecutionBuilder.class);
        when(runtimeService.newMigration(plan)).thenReturn(execBuilder);
        when(execBuilder.processInstanceIds(Collections.singletonList("inst-1"))).thenReturn(execBuilder);
        
        doThrow(new RuntimeException("test exception")).when(execBuilder).execute();
        
        engine.migrateProcessInstances(repositoryService, runtimeService);
        
        verify(execBuilder).execute();
    }
}

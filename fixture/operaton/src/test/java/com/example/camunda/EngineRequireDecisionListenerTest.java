package com.example.camunda;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.dmn.engine.DmnDecisionResult;
import org.operaton.bpm.engine.delegate.BpmnError;
import org.operaton.bpm.engine.delegate.DelegateExecution;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.mock;

@ExtendWith(MockitoExtension.class)
public class EngineRequireDecisionListenerTest {

    @Mock
    private DelegateExecution execution;

    @Test
    void testNotify_NullResult_ThrowsBpmnError() {
        EngineRequireDecisionListener listener = new EngineRequireDecisionListener();
        when(execution.getVariableLocal("decisionResult")).thenReturn(null);

        BpmnError error = assertThrows(BpmnError.class, () -> listener.notify(execution));
        assertEquals("DecisionError", error.getErrorCode());
        assertEquals("No 'decisionResult' variable", error.getMessage());
    }

    @Test
    void testNotify_EmptyResult_ThrowsBpmnError() {
        EngineRequireDecisionListener listener = new EngineRequireDecisionListener();
        DmnDecisionResult result = mock(DmnDecisionResult.class);
        when(result.size()).thenReturn(0);
        when(execution.getVariableLocal("decisionResult")).thenReturn(result);

        BpmnError error = assertThrows(BpmnError.class, () -> listener.notify(execution));
        assertEquals("DecisionError", error.getErrorCode());
        assertEquals("Decision result required", error.getMessage());
    }

    @Test
    void testNotify_NonEmptyResult_DoesNotThrow() {
        EngineRequireDecisionListener listener = new EngineRequireDecisionListener();
        DmnDecisionResult result = mock(DmnDecisionResult.class);
        when(result.size()).thenReturn(1);
        when(execution.getVariableLocal("decisionResult")).thenReturn(result);

        assertDoesNotThrow(() -> listener.notify(execution));
    }
}

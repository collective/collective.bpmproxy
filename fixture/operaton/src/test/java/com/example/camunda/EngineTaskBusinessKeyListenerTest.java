package com.example.camunda;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.engine.delegate.DelegateExecution;

import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
public class EngineTaskBusinessKeyListenerTest {

    @Mock
    private DelegateExecution execution;

    @Test
    void testNotify() throws Exception {
        EngineTaskBusinessKeyListener listener = new EngineTaskBusinessKeyListener();
        when(execution.getBusinessKey()).thenReturn("my-business-key");

        listener.notify(execution);

        verify(execution).setVariableLocal("businessKey", "my-business-key");
    }
}

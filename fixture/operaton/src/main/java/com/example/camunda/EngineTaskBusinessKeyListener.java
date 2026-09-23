package com.example.camunda;

import org.operaton.bpm.engine.delegate.DelegateExecution;
import org.operaton.bpm.engine.delegate.ExecutionListener;

public class EngineTaskBusinessKeyListener implements ExecutionListener {
    public void notify(DelegateExecution execution) throws Exception {
        String businessKey = execution.getBusinessKey();
        execution.setVariableLocal("businessKey", businessKey);
    }
}

package com.example.camunda;

import org.camunda.bpm.engine.delegate.DelegateExecution;
import org.camunda.bpm.engine.delegate.ExecutionListener;

public class EngineTaskBusinessKeyListener implements ExecutionListener {
    public void notify(DelegateExecution execution) throws Exception {
        String businessKey = execution.getBusinessKey();
        execution.setVariableLocal("businessKey", businessKey);
    }
}

package com.example.camunda;

import org.camunda.bpm.dmn.engine.DmnDecisionResult;
import org.camunda.bpm.engine.delegate.DelegateExecution;
import org.camunda.bpm.engine.delegate.ExecutionListener;

public class EngineRequireDecisionListener implements ExecutionListener {
    public void notify(DelegateExecution execution) throws Exception {
        DmnDecisionResult result = (DmnDecisionResult) execution.getVariableLocal("decisionResult");
        if (result != null) {
            if (result.size() == 0) {
                throw new org.camunda.bpm.engine.delegate.BpmnError("DecisionError", "Decision result required");
            }
        } else {
            throw new org.camunda.bpm.engine.delegate.BpmnError("DecisionError", "No 'decisionResult' variable");
        }
    }
}

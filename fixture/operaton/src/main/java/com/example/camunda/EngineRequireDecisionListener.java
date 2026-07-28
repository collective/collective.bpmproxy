package com.example.camunda;

import org.operaton.bpm.dmn.engine.DmnDecisionResult;
import org.operaton.bpm.engine.delegate.DelegateExecution;
import org.operaton.bpm.engine.delegate.ExecutionListener;

public class EngineRequireDecisionListener implements ExecutionListener {
    public void notify(DelegateExecution execution) throws Exception {
        DmnDecisionResult result = (DmnDecisionResult) execution.getVariableLocal("decisionResult");
        if (result == null) {
            throw new org.operaton.bpm.engine.delegate.BpmnError("DecisionError", "No 'decisionResult' variable");
        } else {
            if (result.size() == 0) {
                throw new org.operaton.bpm.engine.delegate.BpmnError("DecisionError", "Decision result required");
            }
        }
    }
}

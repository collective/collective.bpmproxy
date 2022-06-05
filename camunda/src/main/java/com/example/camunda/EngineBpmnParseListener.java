package com.example.camunda;

import org.camunda.bpm.engine.delegate.ExecutionListener;
import org.camunda.bpm.engine.impl.bpmn.parser.AbstractBpmnParseListener;
import org.camunda.bpm.engine.impl.pvm.process.ActivityImpl;
import org.camunda.bpm.engine.impl.pvm.process.ScopeImpl;
import org.camunda.bpm.engine.impl.util.xml.Element;

public class EngineBpmnParseListener extends AbstractBpmnParseListener {

    protected EngineRequireDecisionListener engineRequireDecisionListener;

    public EngineBpmnParseListener() {
        this.engineRequireDecisionListener = new EngineRequireDecisionListener();
    }

    @Override
    public void parseBusinessRuleTask(Element businessRuleTaskElement, ScopeImpl scope, ActivityImpl activity) {
        activity.addListener(ExecutionListener.EVENTNAME_END, engineRequireDecisionListener);
    }
}


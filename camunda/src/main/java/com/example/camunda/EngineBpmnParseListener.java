package com.example.camunda;

import org.camunda.bpm.engine.delegate.ExecutionListener;
import org.camunda.bpm.engine.impl.bpmn.parser.AbstractBpmnParseListener;
import org.camunda.bpm.engine.impl.pvm.process.ActivityImpl;
import org.camunda.bpm.engine.impl.pvm.process.ScopeImpl;
import org.camunda.bpm.engine.impl.util.xml.Element;
import org.camunda.bpm.engine.impl.util.xml.Namespace;

public class EngineBpmnParseListener extends AbstractBpmnParseListener {

    protected EngineRequireDecisionListener engineRequireDecisionListener;
    protected EngineTaskBusinessKeyListener engineTaskBusinessKeyListener;

    public EngineBpmnParseListener() {
        this.engineRequireDecisionListener = new EngineRequireDecisionListener();
        this.engineTaskBusinessKeyListener = new EngineTaskBusinessKeyListener();
    }

    @Override
    public void parseBusinessRuleTask(Element businessRuleTaskElement, ScopeImpl scope, ActivityImpl activity) {
        final Namespace ns = new Namespace("http://camunda.org/schema/1.0/bpmn");
        final String resultType = businessRuleTaskElement.attributeNS(ns, "mapDecisionResult");
        if (resultType.equals("singleEntry") || resultType.equals("singleResult")) {
            activity.addListener(ExecutionListener.EVENTNAME_END, engineRequireDecisionListener);
        }
    }

    @Override
    public void parseUserTask(Element taskElement, ScopeImpl scope, ActivityImpl activity) {
        activity.addListener(ExecutionListener.EVENTNAME_START, engineTaskBusinessKeyListener);
    }
}


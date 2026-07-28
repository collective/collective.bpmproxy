package com.example.camunda;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.operaton.bpm.engine.delegate.ExecutionListener;
import org.operaton.bpm.engine.impl.pvm.process.ActivityImpl;
import org.operaton.bpm.engine.impl.pvm.process.ScopeImpl;
import org.operaton.bpm.engine.impl.util.xml.Element;
import org.operaton.bpm.engine.impl.util.xml.Namespace;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class EngineBpmnParseListenerTest {

    @Mock
    private Element element;
    
    @Mock
    private ScopeImpl scope;
    
    @Mock
    private ActivityImpl activity;

    @Test
    void testParseBusinessRuleTask_SingleEntry() {
        EngineBpmnParseListener listener = new EngineBpmnParseListener();
        when(element.attributeNS(any(Namespace.class), eq("mapDecisionResult"))).thenReturn("singleEntry");
        
        listener.parseBusinessRuleTask(element, scope, activity);
        
        verify(activity).addListener(eq(ExecutionListener.EVENTNAME_END), any(EngineRequireDecisionListener.class));
    }

    @Test
    void testParseBusinessRuleTask_SingleResult() {
        EngineBpmnParseListener listener = new EngineBpmnParseListener();
        when(element.attributeNS(any(Namespace.class), eq("mapDecisionResult"))).thenReturn("singleResult");
        
        listener.parseBusinessRuleTask(element, scope, activity);
        
        verify(activity).addListener(eq(ExecutionListener.EVENTNAME_END), any(EngineRequireDecisionListener.class));
    }

    @Test
    void testParseBusinessRuleTask_OtherResultType() {
        EngineBpmnParseListener listener = new EngineBpmnParseListener();
        when(element.attributeNS(any(Namespace.class), eq("mapDecisionResult"))).thenReturn("collectEntries");
        
        listener.parseBusinessRuleTask(element, scope, activity);
        
        verify(activity, never()).addListener(anyString(), any(ExecutionListener.class));
    }

    @Test
    void testParseBusinessRuleTask_NullResultType() {
        EngineBpmnParseListener listener = new EngineBpmnParseListener();
        when(element.attributeNS(any(Namespace.class), eq("mapDecisionResult"))).thenReturn(null);
        
        listener.parseBusinessRuleTask(element, scope, activity);
        
        verify(activity, never()).addListener(anyString(), any(ExecutionListener.class));
    }

    @Test
    void testParseUserTask() {
        EngineBpmnParseListener listener = new EngineBpmnParseListener();
        
        listener.parseUserTask(element, scope, activity);
        
        verify(activity).setScope(true);
        verify(activity).addListener(eq(ExecutionListener.EVENTNAME_START), any(EngineTaskBusinessKeyListener.class));
    }
}

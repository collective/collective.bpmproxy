package com.example.camunda;

import info.novatec.micronaut.camunda.bpm.feature.Configuration;
import info.novatec.micronaut.camunda.bpm.feature.rest.JettyServerCustomizerRuntimeRest;
import io.micronaut.context.annotation.Replaces;
import io.micronaut.context.annotation.Requires;
import jakarta.inject.Singleton;
import org.camunda.bpm.engine.rest.security.auth.ProcessEngineAuthenticationFilter;
import org.eclipse.jetty.server.Handler;
import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.server.handler.HandlerCollection;
import org.eclipse.jetty.servlet.FilterHolder;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.EnumSet;

import static javax.servlet.DispatcherType.REQUEST;

@Singleton
@Requires(beans = Server.class)
@Requires(property = "camunda.rest.enabled", value = "true")
// Must replace to ensure extra filter right after REST servlet
@Replaces(JettyServerCustomizerRuntimeRest.class)
public class JettyServerCustomizer extends JettyServerCustomizerRuntimeRest {

    private static final Logger log = LoggerFactory.getLogger(JettyServerCustomizer.class);

    public JettyServerCustomizer(Server server, Configuration configuration) {
        super(server, configuration);
    }

    @Override
    public void execute() throws Exception {
        super.execute();

        for (Handler collection : server.getHandlers()) {
            if (collection instanceof HandlerCollection) {
                for (Handler handler: ((HandlerCollection) collection).getHandlers()) {
                    if (handler instanceof ServletContextHandler) {
                        if (((ServletContextHandler) handler).getContextPath().equals(contextPath)) {
                            FilterHolder filterHolder = new FilterHolder(ProcessEngineAuthenticationFilter.class);
                            filterHolder.setInitParameter("authentication-provider", "com.example.camunda.JWTAuthenticationProvider");
                            ((ServletContextHandler) handler).addFilter(filterHolder, "/*", EnumSet.of(REQUEST));
                        }
                    }
                }
            }
        }
    }
}

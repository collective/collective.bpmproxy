package com.example.camunda;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.operaton.bpm.spring.boot.starter.annotation.EnableProcessApplication;

@SpringBootApplication
@EnableProcessApplication
public class Application {

    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}

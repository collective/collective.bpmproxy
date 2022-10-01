mvn2nix-lock.json: pom.xml
	mvn2nix -vvv --jdk=$(JAVA_HOME) > mvn2nix-lock.json

target/camunda-app-0.1.jar:
	mvn package
	# TODO: figure a way to override maven-shade-plugin config for this
	zip -d target/camunda-app-0.1.jar META-INF/BC1024KE.SF
	zip -d target/camunda-app-0.1.jar META-INF/BC1024KE.DSA
	zip -d target/camunda-app-0.1.jar META-INF/BC2048KE.SF
	zip -d target/camunda-app-0.1.jar META-INF/BC2048KE.DSA

###

.PHONY: nix-%
nix-%:
	@echo "run inside nix-shell: $*"
	nix-shell --pure --run "$(MAKE) $*"

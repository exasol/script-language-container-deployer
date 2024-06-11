# Unreleased

## Added

* Integration tests for class `LanguageContainerDeployer` and CLI-function `language_container_deployer_main`.
* Started using the bucket-fs PathLike interface.
* Added support SaaS backend
* Added the container deployment validation functions. This includes waiting until the deployment appears to be completed. The deployer now by default uses this functionality.

## Refactorings

* #15: Used plugin pytest-saas

# Unreleased

## Added
    - Integration tests for the LanguageContainerDeployer class
      and the cli function - language_container_deployer_main.

    - Started using the bucket-fs PathLike interface.

    - Added support SaaS backend

    - Added the container deployment validation functions. This includes
      waiting until the deployment appears to be completed. The deployer
      now by default uses this functionality.

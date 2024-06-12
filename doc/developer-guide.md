# Python Extension Common (PEC) Developer Guide

## Pytest Plugins

PEC declares a dependency to pytest plugin `pytest-exasol-saas` which are maintained in GitHub repository [pytest-plugins/pytest_saas](https://github.com/exasol/pytest-plugins/tree/main/pytest-saas/).

This plugin makes additional fixtures available that are used in the integration tests of PEC.
See files in folder [test/integration](../tree/main/test/integration):

* `conftest.py`
* `test_language_container_deployer_saas.py`
* `test_language_container_deployer_saas_cli.py`

## Running Tests in CI Builds

The test cases in PEC are separated in two groups.

| Group                       | Execution                               | Name of gating GitHub workflow |
|-----------------------------|-----------------------------------------|--------------------------------|
| G1) Fast and cheap tests    | On each push to your development branch | Gate 1 - Regular CI            |
| G2) Slow or expensive tests | Only on manual approval, see below      | Gate 2 - Allow Merge           |

This enables fast development cycles while still protecting the main branch against build failures.

For PEC group G2 particularly contains the tests involving Exasol SaaS infrastructure which are creating costs for the database instances temporarily created during test execution.

Group G2 is guarded by a dedicated [GitHub Enviroment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment#required-reviewers) requiring **manual approval** before these tests are executed.

Each of the groups results in a final gating GitHub workflow job that is added to the branch protection of branch `main`.

So in order to merge a branch to `main` branch, the tests of both groups need to be executed and to have terminated succesfully.

### Approving Slow Tests

To approve executing the tests in group G2
* Open your pull request in GitHub
* Scroll to section "Checks"
* Locate pending tasks, e.g. "Ask if Slow or Expensive Tests (e.g. SaaS) Should be Run"
* Click the link "Details" on the right-hand side
* Click "Review pending Deplopyments"
* Select the checkbox "slow-tests"
* Click the green button "Approve and deploy"

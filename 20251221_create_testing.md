# Smart Test Generation - Design Document

**Date:** December 21, 2024  
**Status:** Planning  
**Priority:** Future Enhancement

---

## Overview

Generate meaningful JUnit tests that validate the Java code does what the COBOL code did. Uses AI to understand business logic from procedure model and generate real assertions.

---

## Two Node Approach

### Node 1: Test Stubs (Quick, No AI)

**Purpose:** Scaffolding for CI/CD pipeline

| Attribute | Value |
|-----------|-------|
| Category | Generate |
| AI Required | No |
| Cost | Free |
| Speed | Fast |

**Input:**
- Java code from Refactor/Packaging

**Output:**
- Test class per service
- `@BeforeEach` setup with mocks
- Empty test method for each public method
- Compiles and runs (tests fail with TODO)

**Example Output:**
```java
@Test
@DisplayName("Should validate customer")
void validateCustomer_shouldValidate() {
    // TODO: Implement test
    fail("Not implemented");
}
```

**Use Case:** Customer wants CI pipeline setup, will write assertions themselves.

---

### Node 2: Smart Tests (AI-Powered)

**Purpose:** Meaningful validation with real assertions

| Attribute | Value |
|-----------|-------|
| Category | Generate |
| AI Required | Yes (Bedrock Claude) |
| Cost | Per-method AI calls |
| Speed | Slower (parallel processing) |

**Inputs:**
1. **Procedure Model** (from Code Analysis) - What COBOL does
2. **Data Model** (from Code Analysis) - Field definitions
3. **Java Code** (from Refactor) - What we generated

**Output:**
- JUnit tests with real assertions
- Validation tests from copybook constraints
- Edge case tests
- Integration tests (optional)

---

## How Smart Tests Work

### Step 1: Read Procedure Model

From Code Analysis JSON:
```json
{
  "procedure_name": "3100-VALIDATE-CUSTOMER",
  "purpose": "Validates customer name fields",
  "conditions": [
    "CA-FIRST-NAME = SPACES",
    "CA-LAST-NAME = SPACES"
  ],
  "actions": [
    "MOVE 'Y' TO WS-HAS-ERROR",
    "MOVE 'First name required' TO WS-ERROR-MSG"
  ]
}
```

### Step 2: Read Generated Java

```java
public void validateCustomer(Customer customer) {
    if (customer.getFirstName() == null || customer.getFirstName().isBlank()) {
        this.hasError = true;
        this.errorMsg = "First name is required";
    }
    if (customer.getLastName() == null || customer.getLastName().isBlank()) {
        this.hasError = true;
        this.errorMsg = "Last name is required";
    }
}
```

### Step 3: AI Generates Tests

```java
@Test
@DisplayName("validateCustomer sets error when first name blank")
void validateCustomer_blankFirstName_setsError() {
    Customer customer = new Customer();
    customer.setFirstName("");
    customer.setLastName("Smith");
    
    service.validateCustomer(customer);
    
    assertTrue(service.isHasError());
    assertEquals("First name is required", service.getErrorMsg());
}

@Test
@DisplayName("validateCustomer sets error when last name blank")
void validateCustomer_blankLastName_setsError() {
    Customer customer = new Customer();
    customer.setFirstName("John");
    customer.setLastName("");
    
    service.validateCustomer(customer);
    
    assertTrue(service.isHasError());
    assertEquals("Last name is required", service.getErrorMsg());
}

@Test
@DisplayName("validateCustomer passes for valid customer")
void validateCustomer_validCustomer_noError() {
    Customer customer = new Customer();
    customer.setFirstName("John");
    customer.setLastName("Smith");
    
    service.validateCustomer(customer);
    
    assertFalse(service.isHasError());
}
```

---

## Copybook to Validation Tests

COBOL copybooks define field constraints that become Java validation tests.

### COBOL Definition:
```cobol
01 CUSTOMER-RECORD.
   05 CUST-ID         PIC 9(10).
   05 CUST-NAME       PIC X(50).
   05 CUST-BALANCE    PIC S9(9)V99.
   05 CUST-STATUS     PIC X(1).
      88 CUST-ACTIVE  VALUE 'A'.
      88 CUST-INACTIVE VALUE 'I'.
```

### AI Generates Boundary Tests:
```java
@Test
@DisplayName("Customer ID max 10 digits - from COBOL PIC 9(10)")
void customerId_max10Digits() {
    customer.setId(9999999999L);
    assertValid(customer);
    
    customer.setId(10000000000L);
    assertInvalid(customer, "id exceeds 10 digits");
}

@Test
@DisplayName("Customer name max 50 chars - from COBOL PIC X(50)")
void customerName_max50Chars() {
    customer.setName("A".repeat(50));
    assertValid(customer);
    
    customer.setName("A".repeat(51));
    assertInvalid(customer, "name exceeds 50 characters");
}

@Test
@DisplayName("Customer status only A or I - from COBOL 88-level")
void customerStatus_onlyAorI() {
    customer.setStatus('A');
    assertValid(customer);
    
    customer.setStatus('I');
    assertValid(customer);
    
    customer.setStatus('X');
    assertInvalid(customer, "invalid status value");
}

@Test
@DisplayName("Customer balance handles signed decimal - from COBOL S9(9)V99")
void customerBalance_signedDecimal() {
    customer.setBalance(new BigDecimal("999999999.99"));
    assertValid(customer);
    
    customer.setBalance(new BigDecimal("-999999999.99"));
    assertValid(customer);  // Signed allowed
    
    customer.setBalance(new BigDecimal("9999999999.99"));
    assertInvalid(customer, "balance exceeds 9 digits");
}
```

---

## Workflow Integration

```
[Code Analysis] 
    ├── procedure_model.json (what COBOL does)
    ├── data_model.json (field definitions)
    └── copybook analysis (constraints)
              ↓
[Code Refactor] → Java code (modernized)
              ↓
[Java Packaging] → Spring Boot project
              ↓
[Test Stubs] → Quick scaffold (optional)
              ↓
[Smart Tests] → AI-generated tests (optional)
              ↓
[Final Package] → Includes tests
```

---

## Node Configuration

### Test Stubs Node

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| framework | select | junit5 | JUnit 5, TestNG |
| include_mocks | boolean | true | Add Mockito mocks |
| fail_on_todo | boolean | true | Tests fail until implemented |

### Smart Tests Node

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| framework | select | junit5 | JUnit 5, TestNG |
| mock_framework | select | mockito | Mockito, MockK |
| unit_tests | boolean | true | Generate unit tests |
| validation_tests | boolean | true | Tests from copybook constraints |
| integration_tests | boolean | false | Controller integration tests |
| coverage_target | select | 80 | 60%, 80%, 100% |
| max_ai_calls | number | 50 | Cost control limit |

---

## Implementation Considerations

| Concern | Solution |
|---------|----------|
| AI cost | Parallel processing (4 workers), max call limit |
| Tests don't compile | Validation step - try compile, fix errors |
| Large codebase | Process per-method, batch requests |
| Test quality | Use procedure model as source of truth |
| Test naming | Follow conventions: methodName_condition_expectedResult |

---

## API Endpoints (Future)

```
POST /test-generation/stubs
  - scout_account_id
  - application_name
  - options: { framework, include_mocks, fail_on_todo }

POST /test-generation/smart
  - scout_account_id
  - application_name
  - options: { framework, coverage_target, max_ai_calls, ... }

GET /test-generation/{job_id}/status
GET /test-generation/{job_id}/results
GET /test-generation/{job_id}/coverage
```

---

## Success Criteria

1. **Test Stubs:** Generate compiling tests in < 30 seconds
2. **Smart Tests:** Generate meaningful tests with 80%+ method coverage
3. **Validation Tests:** Cover all copybook constraints
4. **Cost Control:** Stay within max_ai_calls limit
5. **Quality:** Tests should catch real bugs in generated Java

---

## Next Steps

1. [ ] Design Test Stubs node (no AI)
2. [ ] Design Smart Tests node (AI)
3. [ ] Create API endpoints
4. [ ] Create UI nodes
5. [ ] Create executors
6. [ ] Test with real COBOL → Java output
7. [ ] Measure test quality and coverage

---

*Document created: December 21, 2024*
*Status: Ready for implementation when prioritized*

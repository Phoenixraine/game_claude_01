#include <cstdio>
#include <cstring>

#include "TestFramework.h"

int main(int argc, char** argv) {
  const char* filter = argc > 1 ? argv[1] : "";
  int ran = 0;
  int failedTests = 0;
  for (const ivtest::TestCase& t : ivtest::Registry()) {
    char full[256];
    std::snprintf(full, sizeof(full), "%s.%s", t.module, t.name);
    if (filter[0] != '\0' && std::strstr(full, filter) == nullptr) continue;
    const int before = ivtest::FailureCount();
    t.fn();
    ++ran;
    const bool ok = ivtest::FailureCount() == before;
    if (!ok) ++failedTests;
    std::printf("[%s] %s\n", ok ? " OK " : "FAIL", full);
  }
  std::printf("\n%d tests, %d checks, %d failed tests, %d failed checks\n", ran, ivtest::CheckCount(), failedTests,
              ivtest::FailureCount());
  if (ran == 0) {
    std::printf("no tests matched filter '%s'\n", filter);
    return 2;
  }
  return ivtest::FailureCount() == 0 ? 0 : 1;
}

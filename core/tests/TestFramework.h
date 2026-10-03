// Minimal dependency-free test framework (no gtest: the build must work offline).
//
//   IV_TEST(Module, Name) { IV_CHECK(1 + 1 == 2); IV_CHECK_EQ(a, b); IV_CHECK_NEAR(x, y, eps); }
//
// Tests register themselves; test_main.cpp runs the ones whose "Module.Name" contains the filter
// given on the command line. ctest registers one run per module.
#pragma once

#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

namespace ivtest {

struct TestCase {
  const char* module;
  const char* name;
  void (*fn)();
};

inline std::vector<TestCase>& Registry() {
  static std::vector<TestCase> r;
  return r;
}

struct Registrar {
  Registrar(const char* module, const char* name, void (*fn)()) { Registry().push_back({module, name, fn}); }
};

inline int& FailureCount() {
  static int n = 0;
  return n;
}
inline int& CheckCount() {
  static int n = 0;
  return n;
}

}  // namespace ivtest

#define IV_TEST(module, name)                                              \
  static void iv_test_##module##_##name();                                 \
  static ::ivtest::Registrar iv_reg_##module##_##name(#module, #name, &iv_test_##module##_##name); \
  static void iv_test_##module##_##name()

#define IV_CHECK(cond)                                                                    \
  do {                                                                                    \
    ++::ivtest::CheckCount();                                                             \
    if (!(cond)) {                                                                        \
      ++::ivtest::FailureCount();                                                         \
      std::printf("    CHECK FAILED %s:%d: %s\n", __FILE__, __LINE__, #cond);             \
    }                                                                                     \
  } while (0)

#define IV_CHECK_EQ(a, b)                                                                 \
  do {                                                                                    \
    ++::ivtest::CheckCount();                                                             \
    const auto iv_a = (a);                                                                \
    const auto iv_b = (b);                                                                \
    if (!(iv_a == iv_b)) {                                                                \
      ++::ivtest::FailureCount();                                                         \
      std::printf("    CHECK_EQ FAILED %s:%d: %s == %s (%lld vs %lld)\n", __FILE__, __LINE__, #a, #b, \
                  static_cast<long long>(iv_a), static_cast<long long>(iv_b));             \
    }                                                                                     \
  } while (0)

#define IV_CHECK_NEAR(a, b, eps)                                                          \
  do {                                                                                    \
    ++::ivtest::CheckCount();                                                             \
    const double iv_a = static_cast<double>(a);                                           \
    const double iv_b = static_cast<double>(b);                                           \
    if (!(std::fabs(iv_a - iv_b) <= static_cast<double>(eps))) {                          \
      ++::ivtest::FailureCount();                                                         \
      std::printf("    CHECK_NEAR FAILED %s:%d: %s ~ %s (%g vs %g)\n", __FILE__, __LINE__, #a, #b, iv_a, iv_b); \
    }                                                                                     \
  } while (0)

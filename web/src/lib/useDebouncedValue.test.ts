import { renderHook, act } from "@testing-library/react";
import { useDebouncedValue } from "./useDebouncedValue";

test("retrasa la propagación del valor hasta que pasan ms sin cambios", () => {
  vi.useFakeTimers();
  try {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, 250), { initialProps: { value: "a" } });
    expect(result.current).toBe("a");

    rerender({ value: "ab" });
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("a");

    rerender({ value: "abc" });
    act(() => vi.advanceTimersByTime(200));
    expect(result.current).toBe("a");

    act(() => vi.advanceTimersByTime(250));
    expect(result.current).toBe("abc");
  } finally {
    vi.useRealTimers();
  }
});

test("no retrasa el valor inicial", () => {
  vi.useFakeTimers();
  try {
    const { result } = renderHook(() => useDebouncedValue(42, 250));
    expect(result.current).toBe(42);
  } finally {
    vi.useRealTimers();
  }
});

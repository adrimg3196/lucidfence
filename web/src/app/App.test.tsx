import { render } from "@testing-library/react";
import { App } from "./App";

test("App monta sin errores", () => {
  const { container } = render(<App />);
  expect(container).toBeTruthy();
});

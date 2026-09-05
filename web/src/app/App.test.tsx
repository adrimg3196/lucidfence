import { render, screen } from "@testing-library/react";
import { App } from "./App";

test("muestra el título", () => {
  render(<App />);
  expect(screen.getByRole("heading", { name: "LucidFence 2.0" })).toBeInTheDocument();
});

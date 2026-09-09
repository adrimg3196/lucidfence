// @vitest-environment node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { expect, it } from "vitest";

// Exercise the parser resolved by the actual OpenAPI generator, not a presumed
// hoisted js-yaml. Keep this regression small and externally bounded (#434).
const setup = `
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const generatorRequire = createRequire(require.resolve('openapi-typescript'));
const redoclyPath = generatorRequire.resolve('@redocly/openapi-core');
const redocly = require(redoclyPath);
const yaml = createRequire(redoclyPath)('js-yaml');
const empty = 'arr: &arr [' + Array(8).fill('{}').join(', ') + ']\\ntargets:\\n'
  + '  - <<: *arr\\n'.repeat(8);
assert.equal(Buffer.byteLength(empty), 156);
const keyed = 'arr: &arr [{key: value}]\\ntargets:\\n' + '  - <<: *arr\\n'.repeat(2);
const ordinary = 'base: &base {key: value}\\ntarget: {<<: *base}\\n';
`;

for (const parser of ["yaml.load", "redocly.parseYaml"]) {
  for (const [name, check] of [
    ["rejects 64 empty-source visits with budget 1", `assert.throws(() => parse(empty, {maxTotalMergeKeys: 1}), /maxTotalMergeKeys/);`],
    ["rejects keyed merges over budget", `assert.throws(() => parse(keyed, {maxTotalMergeKeys: 1}), /maxTotalMergeKeys/);`],
    ["accepts an ordinary merge within budget", `assert.deepEqual(parse(ordinary, {maxTotalMergeKeys: 2}).target, {key: 'value'});`],
    ["accepts empty merges at their exact budget", `assert.deepEqual(parse(empty, {maxTotalMergeKeys: 64}).targets, Array.from({length: 8}, () => ({})));`],
    ["accepts keyed merges at their exact budget", `assert.deepEqual(parse(keyed, {maxTotalMergeKeys: 4}).targets, [{key: 'value'}, {key: 'value'}]);`],
    ["preserves YAML without merges", `assert.deepEqual(parse('key: value', {maxTotalMergeKeys: 1}), {key: 'value'});`],
  ]) {
    it(`${parser} ${name}`, () => {
      const result = spawnSync(process.execPath, [
        "--max-old-space-size=128", "--input-type=commonjs", "-e",
        setup + `const parse = ${parser};\n` + check,
      ], {
        cwd: fileURLToPath(new URL("..", import.meta.url)),
        timeout: 15_000,
        encoding: "utf8",
      });
      expect(result.error).toBeUndefined();
      expect(result.status, result.stderr).toBe(0);
    }, 20_000);
  }
}

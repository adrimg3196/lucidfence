// Smoke tests para worker.mjs. Sin dependencias nuevas: node:test + node:assert
// (Node 22). fetch global se mockea — no llama a NVD/UPSTREAM reales, ni en
// local ni en CI. Ejecutar: node --test apps/uem-gateway/worker.test.mjs
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import worker from './worker.mjs';

const ENV = { ALLOWED_ORIGIN: 'https://pwa.example', UPSTREAM_BASE_URL: 'https://upstream.example', UPSTREAM_TOKEN: 'tok123' };
const ORIGIN_HEADERS = { origin: 'https://pwa.example' };

let originalFetch;
let mockImpl = async () => new Response('{}', { status: 500 });
before(() => { originalFetch = globalThis.fetch; globalThis.fetch = (...args) => mockImpl(...args); });
after(() => { globalThis.fetch = originalFetch; });

function req(path, init = {}) {
  return new Request(`https://gateway.example${path}`, { headers: ORIGIN_HEADERS, ...init });
}

test('/health no requiere origin y reporta configured', async () => {
  const res = await worker.fetch(new Request('https://gateway.example/health'), ENV);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.configured, true);
});

test('sin origin permitido -> 403', async () => {
  const res = await worker.fetch(new Request('https://gateway.example/v1/fleet'), ENV);
  assert.equal(res.status, 403);
});

test('/v1/cves/enrich sin origin permitido -> 403 (no solo /v1/fleet)', async () => {
  const res = await worker.fetch(new Request('https://gateway.example/v1/cves/enrich'), ENV);
  assert.equal(res.status, 403);
});

test('POST -> 405 read_only_gateway (incluye rutas nuevas)', async () => {
  const res = await worker.fetch(req('/v1/cves/enrich', { method: 'POST' }), ENV);
  assert.equal(res.status, 405);
  assert.equal((await res.json()).error, 'read_only_gateway');
});

test('ruta desconocida -> 404', async () => {
  const res = await worker.fetch(req('/v1/soar/incident'), ENV);
  assert.equal(res.status, 404);
});

test('/v1/fleet sigue funcionando (regresion)', async () => {
  mockImpl = async () => new Response(JSON.stringify({ devices: [{ id: '1', platform: 'ios' }] }), { status: 200 });
  const res = await worker.fetch(req('/v1/fleet'), ENV);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.devices.length, 1);
  assert.equal(body.devices[0].platform, 'ios');
});

test('/v1/cves/enrich agrega byPlatform desde NVD (mock)', async () => {
  mockImpl = async (url) => {
    const term = new URL(url).searchParams.get('keywordSearch');
    if (term === 'apple ios') {
      return new Response(JSON.stringify({ vulnerabilities: [
        { cve: { metrics: { cvssMetricV31: [{ cvssData: { baseSeverity: 'CRITICAL' } }] } } },
        { cve: { metrics: { cvssMetricV31: [{ cvssData: { baseSeverity: 'medium' } }] } } },
      ] }), { status: 200 });
    }
    return new Response(JSON.stringify({ vulnerabilities: [] }), { status: 200 });
  };
  const res = await worker.fetch(req('/v1/cves/enrich'), ENV);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.source, 'NVD');
  assert.deepEqual(body.byPlatform.ios, { cveCount: 2, cveCritical: true });
  assert.deepEqual(body.byPlatform.android, { cveCount: 0, cveCritical: false });
});

test('/v1/cves/enrich lee baseSeverity de CVSSv2 (campo hermano, fuera de cvssData — forma real de NVD)', async () => {
  mockImpl = async (url) => {
    const term = new URL(url).searchParams.get('keywordSearch');
    if (term === 'apple ios') {
      return new Response(JSON.stringify({ vulnerabilities: [
        // forma real verificada contra services.nvd.nist.gov: baseSeverity vive
        // junto a cvssData, no dentro. Si el parser mirase solo dentro de
        // cvssData (como CVSSv3), esto se leeria como '' y nunca marcaria critical.
        { cve: { metrics: { cvssMetricV2: [{ source: 'nvd@nist.gov', type: 'Primary', cvssData: { baseScore: 9.3 }, baseSeverity: 'CRITICAL' }] } } },
      ] }), { status: 200 });
    }
    return new Response(JSON.stringify({ vulnerabilities: [] }), { status: 200 });
  };
  const res = await worker.fetch(req('/v1/cves/enrich'), ENV);
  const body = await res.json();
  assert.deepEqual(body.byPlatform.ios, { cveCount: 1, cveCritical: true });
});

test('/v1/cves/enrich lee CVSSv4.0 (NVD ya emite CVEs solo-v4, verificado en vivo con "microsoft windows")', async () => {
  mockImpl = async (url) => {
    const term = new URL(url).searchParams.get('keywordSearch');
    if (term === 'microsoft windows') {
      return new Response(JSON.stringify({ vulnerabilities: [
        { cve: { metrics: { cvssMetricV40: [{ source: 'nvd@nist.gov', type: 'Primary', cvssData: { baseSeverity: 'CRITICAL' } }] } } },
      ] }), { status: 200 });
    }
    return new Response(JSON.stringify({ vulnerabilities: [] }), { status: 200 });
  };
  const res = await worker.fetch(req('/v1/cves/enrich'), ENV);
  const body = await res.json();
  assert.deepEqual(body.byPlatform.windows, { cveCount: 1, cveCritical: true });
});

test('/v1/cves/enrich tolera NVD caido por excepcion de red (timeout) sin romper la respuesta', async () => {
  mockImpl = async () => { throw new Error('network error'); };
  const res = await worker.fetch(req('/v1/cves/enrich'), ENV);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.deepEqual(body.byPlatform, {}); // best-effort: ninguna plataforma resuelta, no un 500
});

test('/v1/cves/enrich tolera NVD 429 (rate-limit real, no excepcion) sin romper la respuesta', async () => {
  mockImpl = async () => new Response(JSON.stringify({ message: 'rate limit exceeded' }), { status: 429 });
  const res = await worker.fetch(req('/v1/cves/enrich'), ENV);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.deepEqual(body.byPlatform, {});
});

test('/v1/cves/enrich envia NVD_API_KEY como header apiKey cuando esta configurada', async () => {
  let seenHeaders;
  mockImpl = async (url, init) => { seenHeaders = init.headers; return new Response(JSON.stringify({ vulnerabilities: [] }), { status: 200 }); };
  await worker.fetch(req('/v1/cves/enrich'), { ...ENV, NVD_API_KEY: 'secret-key' });
  assert.equal(seenHeaders.apiKey, 'secret-key');
});

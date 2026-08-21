class Lucidfence < Formula
  include Language::Python::Virtualenv

  desc "Open-source local geofencing and explainable UEM/MDM risk control"
  homepage "https://github.com/adrimg3196/lucidfence"
  url "https://github.com/adrimg3196/lucidfence/releases/download/v1.6.0/lucidfence-1.6.0.tar.gz"
  sha256 "85e0d87307cf1b1e3293e2e8b219a316c89210b58042f3ac6a9c3a2b05467dd2"
  license "Apache-2.0"

  depends_on "python@3.11"

  # Pins de requirements.lock del release (solo el runtime base; las
  # dependencias opcionales de OIDC — pyjwt/cryptography — no van en la
  # fórmula: `import jwt` está guardado y la feature es opt-in).
  resource "requests" do
    url "https://files.pythonhosted.org/packages/34/64/8860370b167a9721e8956ae116825caff829224fbca0ca6e7bf8ddef8430/requests-2.33.0.tar.gz"
    sha256 "c7ebc5e8b0f21837386ad0e1c8fe8b829fa5f544d8df3b2253bff14ef29d7652"
  end

  resource "certifi" do
    url "https://files.pythonhosted.org/packages/c9/c7/424b75da314c1045981bd9777432fad05a9e0c69daa4ed7e308bbaffe405/certifi-2026.6.17.tar.gz"
    sha256 "024c88eeec92ca068db80f02b8b07c9cef7b9fe261d1d535abfd5abd6f6af432"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/bd/2a/23f34ec9d04624958e137efdc394888716353190e75f25dd22c7a2c7a8aa/charset_normalizer-3.4.9.tar.gz"
    sha256 "673611bbd43f0810bec0b0f028ddeaaa501190339cac411f347ac76917c3ae7b"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/cd/63/9496c57188a2ee585e0f1db071d75089a11e98aa86eb99d9d7618fc1edce/idna-3.18.tar.gz"
    sha256 "ffb385a7e039654cef1ab9ef32c6fafe283c0c0467bba1d9029738ce4a14a848"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/53/0c/06f8b233b8fd13b9e5ee11424ef85419ba0d8ba0b3138bf360be2ff56953/urllib3-2.7.0.tar.gz"
    sha256 "231e0ec3b63ceb14667c67be60f2f2c40a518cb38b03af60abc813da26505f4c"
  end

  def install
    libexec.install Dir["*"]
    venv = virtualenv_create(libexec/"venv", "python3.11")
    venv.pip_install resources
    # El tarball no trae bin/lucidfence: el entrypoint es lucidfence/cli.py,
    # ejecutado con el python del venv (que ya ve requests y compañía).
    (bin/"lucidfence").write_env_script libexec/"venv/bin/python3",
      "\"#{libexec}/lucidfence/cli.py\"",
      PATH: "#{libexec}/venv/bin:$PATH"
  end

  def caveats
    <<~EOS
      Start LucidFence and open its local interface:
        lucidfence

      Lifecycle commands:
        lucidfence status
        lucidfence stop
        lucidfence doctor

      Local read-only MCP server:
        lucidfence mcp

      The interface binds to 127.0.0.1:8765. Runtime data stays in your
      user application-data directory and is never written into the Cellar.
    EOS
  end

  service do
    run [opt_bin/"lucidfence", "serve", "--host", "127.0.0.1", "--port", "8765"]
    keep_alive true
    log_path var/"log/lucidfence.log"
    error_log_path var/"log/lucidfence.log"
    working_dir opt_libexec
  end

  test do
    port = free_port
    pid = spawn opt_bin/"lucidfence", "serve", "--port", port.to_s
    sleep 4
    page = shell_output("curl -fsS http://127.0.0.1:#{port}/")
    assert_match "LucidFence", page
    assert_match "Command Center", page
    assert_match "lucidfence 1.6.0", shell_output("#{bin}/lucidfence --version")
  ensure
    Process.kill("TERM", pid) if pid
  end
end

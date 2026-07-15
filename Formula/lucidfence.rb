class Lucidfence < Formula
  include Language::Python::Virtualenv

  desc "Open-source local geofencing and explainable UEM/MDM risk control"
  homepage "https://github.com/adrimg3196/lucidfence"
  url "https://github.com/adrimg3196/lucidfence/releases/download/v1.1.0/lucidfence-1.1.0.tar.gz"
  sha256 "b413636af9d153ccd4220c36c150db21abe161e5b4b2f4ace6cf5ece375f89e4"
  license "Apache-2.0"

  depends_on "python@3.11"

  resource "requests" do
    url "https://files.pythonhosted.org/packages/c9/74/b3ff8e6c8446842c3f5c837e9c3dfcfe2018ea6ecef224c710c85ef728f4/requests-2.32.5.tar.gz"
    sha256 "dbba0bac56e100853db0ea71b82b4dfd5fe2bf6d3754a8893c3af500cec7d7cf"
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
    url "https://files.pythonhosted.org/packages/c7/24/5f1b3bdffd70275f6661c76461e25f024d5a38a46f04aaca912426a2b1d3/urllib3-2.6.3.tar.gz"
    sha256 "1b62b6884944a57dbe321509ab94fd4d3b307075e0c2eae991ac71ee15ad38ed"
  end

  def install
    libexec.install Dir["*"]
    venv = virtualenv_create(libexec/"venv", "python3.11")
    venv.pip_install resources
    (bin/"lucidfence").write_env_script libexec/"bin/lucidfence",
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
    assert_match "lucidfence 1.1.0", shell_output("#{bin}/lucidfence --version")
  ensure
    Process.kill("TERM", pid) if pid
  end
end

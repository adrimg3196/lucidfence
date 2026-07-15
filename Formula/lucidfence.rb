class Lucidfence < Formula
  desc "Geofencing soberano para UEM/MDM (on-prem, $0, sin datos en la nube)"
  homepage "https://github.com/adrimg3196/lucidfence"
  url "https://github.com/adrimg3196/lucidfence/releases/download/v1.0.0/lucidfence-1.0.0.tar.gz"
  sha256 "83f3672de9d2b00bac3d85d861964e1ee21065bb8ffebff9c1a69d0a31bf88a5"
  license "Apache-2.0"

  depends_on "python@3.11"

  def install
    # El tarball trae el repo completo bajo el prefijo 'lucidfence/'.
    libexec.install Dir["lucidfence/*"]

    # Crea el binario 'lucidfence' que envuelve bin/lucidfence (CLI on-prem).
    (bin/"lucidfence").write_env_script libexec/"bin/lucidfence",
      PATH: "#{Formula["python@3.11"].opt_bin}:$PATH"

    # requirements.lock para instalacion con hashes (modo Python directo).
    # El modo Docker es opcional; aqui dejamos el stack Python listo.
  end

  service do
    run [opt_bin/"lucidfence", "serve", "--port", "8765"]
    keep_alive true
    log_path var/"log/lucidfence.log"
    error_log_path var/"log/lucidfence.log"
    working_dir var
  end

  test do
    # Arranca y comprueba que el server responde en el puerto elegido.
    port = free_port
    pid = spawn opt_bin/"lucidfence", "serve", "--port", port.to_s
    sleep 3
    assert_match(/LucidFence/, shell_output("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:#{port}/"))
  ensure
    Process.kill("TERM", pid) if pid
  end
end

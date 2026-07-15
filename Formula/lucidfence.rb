class Lucidfence < Formula
  desc "Geofencing soberano para UEM/MDM (on-prem, $0, sin datos en la nube)"
  homepage "https://github.com/adrimg3196/lucidfence"
  url "https://github.com/adrimg3196/lucidfence/releases/download/v1.0.4/lucidfence-1.0.4.tar.gz"
  sha256 "dc17b45a6e8258314a4308e78f2d69471cd7a05757f4b14a63372876d4ba6090"
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

  def post_install
    # Copia la .app nativa a ~/Applications para que el usuario la tenga
    # en el Launchpad (launcher arranca el server y abre el navegador).
    app = libexec/"macos/LucidFence.app"
    if app.exist?
      dest = Path("#{Dir.home}/Applications/LucidFence.app")
      dest.parent.mkpath
      rm_rf dest if dest.exist?
      cp_r app, dest
    end
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

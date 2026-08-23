Z.A.R.V.I.S. Owner Domain

Primary console:
  https://zarvis.zeaz.dev

Proactive console:
  https://proactive.zarvis.zeaz.dev

Security:
  - Linux HTTPS gateway listens only on 127.0.0.1:8443.
  - Windows forwards only 127.0.0.1:443 over encrypted SSH.
  - These names are mapped only in the owner's Windows hosts file.
  - No public DNS record or public HTTP ingress is required.
  - Owner Token remains required by the Z.A.R.V.I.S. console.
  - The private CA key stays on the Linux server and is not in this bundle.

Install:
  Double-click Install-ZARVIS-OwnerDomain.cmd.
  Enter the Linux SSH password once only when the installer needs to authorize
  the generated Windows SSH key.

Uninstall:
  Run PowerShell as Administrator:
  powershell -ExecutionPolicy Bypass -File .\Uninstall-ZARVIS-OwnerDomain.ps1

const secretEnvironmentVariables = [
  'ZARVIS_LOCAL_OWNER_TOKEN',
  'ZARVIS_ACTION_WORKER_TOKEN',
  'ZARVIS_PROACTIVE_WORKER_TOKEN',
];

for (const name of secretEnvironmentVariables) {
  delete process.env[name];
}

const OWNER_PATTERN = /^[A-Za-z0-9_.-]{1,39}$/;
const REPOSITORY_PATTERN = /^[A-Za-z0-9_.-]{1,100}$/;

export const GITHUB_REPOSITORY_STATUS_TOOL = Object.freeze({
  name: 'github.repository.status',
  description: 'Read public or authorized GitHub repository metadata and summarize its current status.',
  access: 'read_only',
  approval_required: false,
  input_schema: {
    type: 'object',
    additionalProperties: false,
    required: ['owner', 'repo'],
    properties: {
      owner: { type: 'string', minLength: 1, maxLength: 39 },
      repo: { type: 'string', minLength: 1, maxLength: 100 },
    },
  },
});

export class GitHubStatusToolError extends Error {
  constructor(message, { code = 'github_status_failed', status = 502, cause } = {}) {
    super(message, { cause });
    this.name = 'GitHubStatusToolError';
    this.code = code;
    this.status = status;
  }
}

function validateTarget({ owner, repo }) {
  if (!OWNER_PATTERN.test(owner) || !REPOSITORY_PATTERN.test(repo)) {
    throw new GitHubStatusToolError('Invalid GitHub repository identifier.', {
      code: 'invalid_repository_identifier',
      status: 400,
    });
  }
}

function normalizeRepositoryPayload(payload) {
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    throw new GitHubStatusToolError('GitHub returned an invalid repository payload.', {
      code: 'invalid_github_response',
    });
  }

  const requiredStrings = ['full_name', 'default_branch', 'visibility', 'updated_at', 'pushed_at'];
  for (const field of requiredStrings) {
    if (typeof payload[field] !== 'string') {
      throw new GitHubStatusToolError(`GitHub response is missing ${field}.`, {
        code: 'invalid_github_response',
      });
    }
  }

  return {
    full_name: payload.full_name,
    visibility: payload.visibility,
    private: Boolean(payload.private),
    archived: Boolean(payload.archived),
    disabled: Boolean(payload.disabled),
    fork: Boolean(payload.fork),
    default_branch: payload.default_branch,
    open_issues_count: Number.isInteger(payload.open_issues_count) ? payload.open_issues_count : 0,
    stargazers_count: Number.isInteger(payload.stargazers_count) ? payload.stargazers_count : 0,
    watchers_count: Number.isInteger(payload.watchers_count) ? payload.watchers_count : 0,
    forks_count: Number.isInteger(payload.forks_count) ? payload.forks_count : 0,
    updated_at: payload.updated_at,
    pushed_at: payload.pushed_at,
    web_url: typeof payload.html_url === 'string' ? payload.html_url : null,
  };
}

export async function executeGitHubRepositoryStatus(
  target,
  {
    fetchImpl = globalThis.fetch,
    token = process.env.GITHUB_TOKEN,
    timeoutMs = Number(process.env.ZARVIS_GITHUB_TIMEOUT_MS ?? 5_000),
  } = {},
) {
  validateTarget(target);

  if (typeof fetchImpl !== 'function') {
    throw new GitHubStatusToolError('No fetch implementation is available.', {
      code: 'fetch_unavailable',
    });
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  timeout.unref?.();

  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'z-platform-zarvis-orchestrator',
    'X-GitHub-Api-Version': '2022-11-28',
  };
  if (typeof token === 'string' && token.trim()) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }

  const url = new URL(`https://api.github.com/repos/${encodeURIComponent(target.owner)}/${encodeURIComponent(target.repo)}`);

  try {
    const response = await fetchImpl(url, {
      method: 'GET',
      headers,
      redirect: 'error',
      signal: controller.signal,
    });

    if (!response.ok) {
      if (response.status === 404) {
        throw new GitHubStatusToolError('Repository was not found or is not accessible.', {
          code: 'repository_not_found',
          status: 404,
        });
      }
      if (response.status === 401 || response.status === 403) {
        throw new GitHubStatusToolError('GitHub authorization failed or the rate limit was exceeded.', {
          code: 'github_authorization_failed',
          status: 502,
        });
      }
      throw new GitHubStatusToolError(`GitHub returned HTTP ${response.status}.`, {
        code: 'github_upstream_error',
        status: 502,
      });
    }

    return normalizeRepositoryPayload(await response.json());
  } catch (error) {
    if (error instanceof GitHubStatusToolError) {
      throw error;
    }
    if (error?.name === 'AbortError') {
      throw new GitHubStatusToolError('GitHub request timed out.', {
        code: 'github_timeout',
        status: 504,
        cause: error,
      });
    }
    throw new GitHubStatusToolError('GitHub request failed.', {
      code: 'github_network_error',
      status: 502,
      cause: error,
    });
  } finally {
    clearTimeout(timeout);
  }
}

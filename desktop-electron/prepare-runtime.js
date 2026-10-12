const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const root = path.resolve(__dirname, '..');
const standalone = path.join(root, 'frontend', '.next', 'standalone');
if (!fs.existsSync(path.join(standalone, 'server.js'))) {
  throw new Error('Build frontend first: cd ../frontend && npm run build (Next output: standalone)');
}

const target = path.join(__dirname, 'runtime');
fs.mkdirSync(target, { recursive: true });

// 1. Stage Next.js standalone frontend
fs.cpSync(standalone, path.join(target, 'frontend'), { recursive: true });
fs.cpSync(path.join(root, 'frontend', '.next', 'static'), path.join(target, 'frontend', '.next', 'static'), { recursive: true });
const publicDir = path.join(root, 'frontend', 'public');
if (fs.existsSync(publicDir)) fs.cpSync(publicDir, path.join(target, 'frontend', 'public'), { recursive: true });

// 2. Stage FastAPI backend
fs.mkdirSync(path.join(target, 'backend'), { recursive: true });
fs.cpSync(path.join(root, 'backend', 'app'), path.join(target, 'backend', 'app'), {
  recursive: true,
  filter: source => !source.split(path.sep).includes('__pycache__') && !source.endsWith('.pyc')
});
fs.copyFileSync(path.join(root, 'backend', 'requirements.txt'), path.join(target, 'backend', 'requirements.txt'));

// 3. Stage embedded standalone Python 3.12 + pre-installed site-packages so end-users never wait for pip install
const venvPython = process.env.PDF_TOOLKIT_PYTHON || path.join(root, '.venv-test', 'Scripts', 'python.exe');
const targetPythonDir = path.join(target, 'python');
const targetSpDir = path.join(targetPythonDir, 'Lib', 'site-packages');

if (fs.existsSync(venvPython)) {
  const basePrefix = execFileSync(venvPython, ['-c', 'import sys; print(sys.base_prefix)'], { encoding: 'utf8' }).trim();
  const baseSitePackages = path.join(basePrefix, 'Lib', 'site-packages');
  const venvSitePackages = path.join(path.dirname(path.dirname(venvPython)), 'Lib', 'site-packages');

  if (!fs.existsSync(path.join(targetPythonDir, 'python.exe'))) {
    console.log('Staging embedded Python 3.12 runtime into runtime/python...');
    fs.mkdirSync(targetPythonDir, { recursive: true });

    for (const file of ['python.exe', 'pythonw.exe', 'python3.dll', 'python312.dll', 'vcruntime140.dll', 'vcruntime140_1.dll', 'LICENSE.txt']) {
      const src = path.join(basePrefix, file);
      if (fs.existsSync(src)) fs.copyFileSync(src, path.join(targetPythonDir, file));
    }

    const dllsDir = path.join(basePrefix, 'DLLs');
    if (fs.existsSync(dllsDir)) {
      fs.cpSync(dllsDir, path.join(targetPythonDir, 'DLLs'), {
        recursive: true,
        filter: src => !src.endsWith('.pdb')
      });
    }

    const excludedStdlibDirs = new Set(['site-packages', '__pycache__', 'test', 'tests', 'idlelib', 'tkinter', 'turtledemo', 'ensurepip', 'venv']);
    fs.cpSync(path.join(basePrefix, 'Lib'), path.join(targetPythonDir, 'Lib'), {
      recursive: true,
      filter: src => {
        const parts = path.relative(path.join(basePrefix, 'Lib'), src).split(path.sep);
        return !parts.some(p => excludedStdlibDirs.has(p)) && !src.endsWith('.pyc');
      }
    });
  }

  fs.mkdirSync(targetSpDir, { recursive: true });
  const copyFilter = src => !src.split(path.sep).includes('__pycache__') && !src.endsWith('.pyc') && !src.endsWith('.pdb');

  // Copy shared packages from basePrefix site-packages
  const basePackages = [
    'PIL', '_cffi_backend.cp312-win_amd64.pyd', '_distutils_hack', 'annotated_types',
    'charset_normalizer', 'cryptography', 'dateutil', 'docx', 'et_xmlfile', 'lxml',
    'numpy', 'numpy.libs', 'openpyxl', 'packaging', 'pandas', 'pandas.libs',
    'pillow.libs', 'pptx', 'pydantic', 'pydantic_core', 'pypdf', 'six.py',
    'typing_extensions.py', 'typing_inspection', 'xlsxwriter'
  ];
  for (const item of basePackages) {
    const src = path.join(baseSitePackages, item);
    const dst = path.join(targetSpDir, item);
    if (fs.existsSync(src) && !fs.existsSync(dst)) {
      fs.cpSync(src, dst, { recursive: true, filter: copyFilter });
    }
  }

  // Copy venv site-packages
  const excludedSpPrefixes = ['pip', 'pytest', '_pytest', 'setuptools', 'pkg_resources', 'pluggy', 'iniconfig'];
  fs.cpSync(venvSitePackages, targetSpDir, {
    recursive: true,
    filter: src => {
      const rel = path.relative(venvSitePackages, src);
      if (!rel) return true;
      const top = rel.split(path.sep)[0];
      if (excludedSpPrefixes.some(prefix => top === prefix || top.startsWith(prefix + '-'))) return false;
      return copyFilter(src);
    }
  });
}

const headPath = path.join(root, '.git', 'refs', 'heads', 'main');
const commitSha = fs.existsSync(headPath) ? fs.readFileSync(headPath, 'utf8').trim() : null;
const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, 'package.json'), 'utf8'));

fs.writeFileSync(path.join(target, 'desktop-runtime.json'), JSON.stringify({
  python: 'python/python.exe',
  version: pkg.version,
  repo: 'khusan-1-lox/pdf-toolkit',
  branch: 'main',
  commitSha,
  builtAt: new Date().toISOString()
}, null, 2));

console.log(`Desktop resources staged in ${target}`);

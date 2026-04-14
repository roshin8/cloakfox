# Testing Firefox 146 Beta

This guide explains how to test the experimental Firefox 146 build of Cloakfox.

> **Note:** The FF146 build is experimental and may contain bugs. For a stable production version, use branch `releases/135`.

## Build from Source

1. Clone the repository:
```bash
git clone --depth 1 https://github.com/daijro/cloakfox
cd cloakfox
```

2. Set up the build environment:
```bash
make dir
make bootstrap   # only needed once
```

3. Build for your target platform:
```bash
python3 multibuild.py --target <os> --arch <arch>
```

| Parameter | Options |
|-----------|---------|
| `--target` | `linux`, `windows`, `macos` |
| `--arch` | `x86_64`, `arm64`, `i686` |

Build artifacts will appear in the `dist/` folder.

### Default Install Directories

When using the Python library (`cloakfox fetch`), the default install directory is:

| OS | Install Directory |
|------|-------------------|
| **Linux** | `~/.cache/cloakfox/` |
| **macOS** | `~/Library/Caches/cloakfox/` |
| **Windows** | `C:\Users\<user>\AppData\Local\cloakfox\cloakfox\Cache\` |

## Replacing the Binary

To test FF146 with an existing Cloakfox installation:

1. Build from source using the instructions above
2. Extract the built zip from `dist/`
3. Replace the binary at the corresponding path for your OS:

**Linux:**
```bash
cp /path/to/built/cloakfox-bin ~/.cache/cloakfox/cloakfox-bin
```

**macOS:**
```bash
cp /path/to/built/Cloakfox.app ~/Library/Caches/cloakfox/Cloakfox.app
```

**Windows:**
```powershell
copy C:\path\to\built\cloakfox.exe C:\Users\<user>\AppData\Local\cloakfox\cloakfox\Cache\cloakfox.exe
```

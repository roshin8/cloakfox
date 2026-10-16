# Gecko CI native runtime inputs

Execute inline; user authorizes implementation, tests, commit and push without plan approval. Preserve active jobs and all uncommitted identity work.

Observed run38880746857 omitted xpcshell, FFVPX headers/corpus and the separately built CPU renderer. The standalone renderer probe also lacked its required directory. Repair artifact provisioning rather than accepting incomplete runs.

- [x] Package only selected same-build native files and codec source inputs; bind archive integrity and commit; reject traversal and links on restore. Verify the handoff with actual native startup and corpus cases.
- [x] Build pinned CPU renderer on its own standard hosted macOS job, install its pinned Clang toolchain and reuse the existing tested live child logger/reserve guard for GN/Ninja. Feed the verified same-run artifact into Gecko source staging.
- [x] Preserve canonical library integrity through leaf/nested signing and final app sealing; verify final signature and manifest. Exercise actual copied libraries in a temporary signing fixture and standalone shader probe.
- [x] Supply explicit native and standalone probe paths. Preserve strict failures and raw upstream warnings.
- [ ] Verify fresh hosted renderer acquisition/compilation, same-run handoffs and full installed sandbox/native runtime. Native CGL offscreen creation failures and unsupported Linux canonical coverage remain distinct unresolved findings; do not waive them to green CI.

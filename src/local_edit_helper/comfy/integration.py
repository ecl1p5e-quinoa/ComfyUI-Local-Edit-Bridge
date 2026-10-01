from pathlib import Path

import folder_paths

from ..core.jobs import JobStore

store = JobStore(Path(folder_paths.get_output_directory()) / "gpt_local_edit" / "jobs")

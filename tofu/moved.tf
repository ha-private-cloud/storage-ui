# Remove once every workspace (default, prv, prd) has applied past this rename.
moved {
  from = helm_release.clusterkeep_ui
  to   = helm_release.storage_ui
}

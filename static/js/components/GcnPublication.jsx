import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import PropTypes from "prop-types";
import { withStyles, makeStyles } from "@mui/styles";
import Dialog from "@mui/material/Dialog";
import DialogContent from "@mui/material/DialogContent";
import MuiDialogTitle from "@mui/material/DialogTitle";
import IconButton from "@mui/material/IconButton";
import Close from "@mui/icons-material/Close";
import Typography from "@mui/material/Typography";
import grey from "@mui/material/colors/grey";
import TextField from "@mui/material/TextField";
import Grid from "@mui/material/Grid";
import Paper from "@mui/material/Paper";
import Checkbox from "@mui/material/Checkbox";
import InputLabel from "@mui/material/InputLabel";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import FormControlLabel from "@mui/material/FormControlLabel";
import LoadingButton from "@mui/lab/LoadingButton";
import dayjs from "dayjs";
import utc from "dayjs/plugin/utc";
import relativeTime from "dayjs/plugin/relativeTime";

import { showNotification } from "baselayer/components/Notifications";
import {
  SelectLabelWithChips,
  SelectSingleLabelWithChips,
} from "./SelectWithChips";

import { fetchGroup } from "../ducks/group";
import { fetchGroups } from "../ducks/groups";
import { fetchInstruments } from "../ducks/instruments";
import {
  postGcnEventPublication,
  fetchGcnEventPublications,
  fetchGcnEventPublication,
  deleteGcnEventPublication,
} from "../ducks/gcnEvent";
import Button from "./Button";
import GcnPublicationTable from "./GcnPublicationTable";
import GcnPublicationEdit from "./GcnPublicationEdit";

dayjs.extend(relativeTime);
dayjs.extend(utc);

const useStyles = makeStyles((theme) => ({
  shortcutButtons: {
    margin: "1rem 0",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    padding: theme.spacing(1),
    alignItems: "left",
    justifyContent: "left",
    height: "100%",
    width: "100%",
    " & > *": {
      marginTop: theme.spacing(2),
      marginBottom: theme.spacing(2),
    },
  },
  content: {
    height: "100%",
    width: "100%",
  },
  textForm: {
    height: "100%",
    width: "100%",
    overflow: "hidden",
  },
  textField: {
    height: "80vh",
    width: "100%",
    overflow: "auto",
  },
  checkboxes: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gridGap: "1rem",
    width: "100%",
    height: "100%",
  },
  button: {
    width: "100%",
  },
  buttons: {
    display: "flex",
    flexDirection: "row",
    width: "100%",
    gap: theme.spacing(2),
  },
  menu: {
    display: "flex",
    direction: "row",
    justifyContent: "space-around",
    alignItems: "center",
    marginBottom: "1rem",
  },
}));

const dialogTitleStyles = (theme) => ({
  root: {
    margin: 0,
    padding: theme.spacing(2),
  },
  title: {
    marginRight: theme.spacing(2),
  },
  closeButton: {
    position: "absolute",
    right: theme.spacing(1),
    top: theme.spacing(1),
    color: grey[500],
  },
});

const DialogTitle = withStyles(dialogTitleStyles)(
  ({ children, classes, onClose }) => (
    <MuiDialogTitle disableTypography className={classes.root}>
      <Typography variant="h6" className={classes.title}>
        {children}
      </Typography>
      {onClose ? (
        <IconButton
          aria-label="close"
          className={classes.closeButton}
          onClick={onClose}
        >
          <Close />
        </IconButton>
      ) : null}
    </MuiDialogTitle>
  )
);

const GcnPublication = ({ dateobs }) => {
  const classes = useStyles();
  const groups = useSelector((state) => state.groups.userAccessible);
  const { instrumentList } = useSelector((state) => state.instruments);
  const dispatch = useDispatch();
  const [open, setOpen] = useState(false);
  const [selectedGroup, setSelectedGroup] = useState(null);
  const gcnEvent = useSelector((state) => state.gcnEvent);
  const [publicationName, setPublicationName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [localizationName, setLocalizationName] = useState(null);
  const [localizationCumprob, setLocalizationCumprob] = useState("0.95");
  const [numberDetections, setNumberDetections] = useState("2");
  const [showSources, setShowSources] = useState(false);
  const [showObservations, setShowObservations] = useState(false);
  const [photometryInWindow, setPhotometryInWindow] = useState(false);
  const [selectedInstruments, setSelectedInstruments] = useState([]);
  const [selectedGcnPublicationId, setSelectedGcnPublicationId] =
    useState(null);

  const [loading, setLoading] = useState(false);

  const groups_list = groups.map((group) => ({
    id: group?.id,
    label: group?.name,
  }));

  let sortedInstrumentList = [...instrumentList];
  sortedInstrumentList.sort((i1, i2) => {
    if (i1.name > i2.name) {
      return 1;
    }
    if (i2.name > i1.name) {
      return -1;
    }
    return 0;
  });

  // to each sortedInstrument, add a label field with the instrument name
  sortedInstrumentList = sortedInstrumentList.map((instrument) => ({
    ...instrument,
    label: instrument?.name,
  }));

  useEffect(() => {
    if (instrumentList?.length === 0) {
      dispatch(fetchInstruments());
    }
  }, []);

  useEffect(() => {
    if (!groups && open) {
      dispatch(fetchGroups());
    }
    const defaultStartDate = dayjs.utc(dateobs).format("YYYY-MM-DD HH:mm:ss");
    const defaultEndDate = dayjs
      .utc(dateobs)
      .add(7, "day")
      .format("YYYY-MM-DD HH:mm:ss");
    setStartDate(defaultStartDate);
    setEndDate(defaultEndDate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateobs, dispatch]);

  useEffect(() => {
    if (selectedGroup?.id) {
      dispatch(fetchGroup(selectedGroup?.id));
    }
  }, [dispatch, selectedGroup]);

  useEffect(() => {
    if (gcnEvent?.localizations?.length > 0) {
      setLocalizationName(gcnEvent?.localizations[0]?.localization_name);
    }
  }, [gcnEvent]);

  useEffect(() => {
    if (dateobs !== null && dateobs !== undefined) {
      dispatch(fetchGcnEventPublications(dateobs));
    }
  }, [dateobs, dispatch]);

  useEffect(() => {
    const fetchPublication = (publicationID) => {
      dispatch(fetchGcnEventPublication({ dateobs, publicationID })).then(
        (response) => {
          if (response.status !== "success") {
            dispatch(showNotification("Error fetching publication", "error"));
          }
        }
      );
    };
    if (
      gcnEvent?.publications?.length > 0 &&
      selectedGcnPublicationId &&
      selectedGcnPublicationId !== gcnEvent?.publication?.id
    ) {
      fetchPublication(selectedGcnPublicationId);
    }
  }, [gcnEvent, selectedGcnPublicationId]);

  const handleClose = () => {
    setOpen(false);
  };

  const onGroupSelectChange = (event) => {
    setSelectedGroup(event.target.value);
  };

  const onInstrumentSelectChange = (event) => {
    let new_selected_instruments = [];
    event.target.value.forEach((instrument) => {
      if (
        !new_selected_instruments.some(
          (selected_instrument) => selected_instrument?.id === instrument?.id
        )
      ) {
        new_selected_instruments.push(instrument);
      } else {
        // remove the user from the list
        new_selected_instruments = new_selected_instruments.filter(
          (selected_instrument) => selected_instrument?.id !== instrument?.id
        );
      }
    });
    setSelectedInstruments(new_selected_instruments);
  };

  const validateSubmit = () => {
    let valid = true;

    if (!startDate) {
      dispatch(showNotification("Please select a start date", "error"));
      valid = false;
    }
    if (!endDate) {
      dispatch(showNotification("Please select an end date", "error"));
      valid = false;
    }
    if (!showSources && !showObservations) {
      dispatch(
        showNotification(
          "Please select at least one type to publish: sources or observations",
          "error"
        )
      );
      valid = false;
    }
    return valid;
  };

  const handleSubmitGcnPublication = async () => {
    if (validateSubmit()) {
      setLoading(true);
      const params = {
        publicationName,
        groupId: selectedGroup?.id,
        startDate,
        endDate,
        localizationName,
        localizationCumprob,
        numberDetections,
        showSources,
        showObservations,
        photometryInWindow,
        instrumentIds: (selectedInstruments || []).map(
          (instrument) => instrument?.id
        ),
      };
      if (params?.instrumentIds?.length === 0) {
        delete params.instrumentIds;
      }
      dispatch(postGcnEventPublication({ dateobs, params })).then(
        (response) => {
          if (response.status === "success") {
            dispatch(
              showNotification("Publication is being generated, please wait")
            );
          } else {
            dispatch(showNotification("Error generating publication", "error"));
          }
          setLoading(false);
        }
      );
    }
  };

  const handleDeleteGcnPublication = (publicationID) => {
    dispatch(deleteGcnEventPublication({ dateobs, publicationID })).then(
      (response) => {
        if (response.status === "success") {
          dispatch(showNotification("Publication deleted"));
        } else {
          dispatch(showNotification("Error deleting publication", "error"));
        }
      }
    );
  };

  return (
    <>
      <Button secondary name="gcn_publication" onClick={() => setOpen(true)}>
        Publication
      </Button>
      {open && (
        <Dialog
          open={open}
          onClose={handleClose}
          style={{ position: "fixed" }}
          fullScreen
        >
          <DialogTitle onClose={handleClose}>Event {dateobs}</DialogTitle>
          <DialogContent dividers>
            <Grid container spacing={3}>
              <Grid item md={4} sm={12}>
                <Paper elevation={1} className={classes.form}>
                  <TextField
                    id="publicationName"
                    label="Publication Name"
                    value={publicationName}
                    onChange={(e) => setPublicationName(e.target.value)}
                  />
                  <SelectSingleLabelWithChips
                    label="Group"
                    id="group-select"
                    initValue={selectedGroup}
                    onChange={onGroupSelectChange}
                    options={groups_list}
                  />
                  <SelectLabelWithChips
                    label="Instruments (Optional)"
                    id="instruments-select"
                    initValue={selectedInstruments}
                    onChange={onInstrumentSelectChange}
                    options={sortedInstrumentList}
                  />
                  <TextField
                    id="startDate"
                    label="Start Date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                  />
                  <TextField
                    id="endDate"
                    label="End Date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                  />
                  <div>
                    <InputLabel id="localizationSelectLabel">
                      Localization Name
                    </InputLabel>
                    <Select
                      inputProps={{ MenuProps: { disableScrollLock: true } }}
                      labelId="localizationSelectLabel"
                      value={localizationName || ""}
                      onChange={(e) => setLocalizationName(e.target.value)}
                      name="gcnPublicationLocalizationSelect"
                    >
                      {gcnEvent.localizations?.map((localization) => (
                        <MenuItem
                          value={localization?.localization_name}
                          key={localization?.localization_name}
                        >
                          {`${localization?.localization_name}`}
                        </MenuItem>
                      ))}
                    </Select>
                  </div>
                  <TextField
                    id="localizationCumprob"
                    label="Localization Cumulative Probability"
                    value={localizationCumprob}
                    onChange={(e) => setLocalizationCumprob(e.target.value)}
                  />
                  <TextField
                    id="numberDetections"
                    label="Minimum Number of Detections"
                    value={numberDetections}
                    onChange={(e) => setNumberDetections(e.target.value)}
                  />
                  <div className={classes.checkboxes}>
                    <FormControlLabel
                      control={
                        <Checkbox
                          label="Show Sources"
                          checked={showSources}
                          onChange={(e) => setShowSources(e.target.checked)}
                        />
                      }
                      label="Show Sources"
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          label="Show Observations"
                          checked={showObservations}
                          onChange={(e) =>
                            setShowObservations(e.target.checked)
                          }
                        />
                      }
                      label="Show Observations"
                    />
                    <FormControlLabel
                      control={
                        <Checkbox
                          label="Photometry in Window (only between start and end dates)"
                          checked={photometryInWindow}
                          onChange={(e) =>
                            setPhotometryInWindow(e.target.checked)
                          }
                        />
                      }
                      label="Photometry in Window (only between start and end dates)"
                    />
                  </div>
                  <div className={classes.buttons}>
                    <LoadingButton
                      onClick={() => handleSubmitGcnPublication()}
                      loading={loading}
                      loadingPosition="end"
                      variant="contained"
                      className={classes.button}
                    >
                      Generate
                    </LoadingButton>
                  </div>
                </Paper>
              </Grid>
              <Grid item md={8} sm={12}>
                <Paper className={classes.menu}>
                  <Button
                    primary
                    id="gcn-publication-list"
                    onClick={() => setSelectedGcnPublicationId(null)}
                  >
                    GCN Publications List
                  </Button>
                </Paper>
                {!selectedGcnPublicationId && (
                  <Paper elevation={1} className={classes.content}>
                    <div>
                      <GcnPublicationTable
                        publications={gcnEvent?.publications}
                        setSelectedGcnPublicationId={
                          setSelectedGcnPublicationId
                        }
                        deleteGcnPublication={handleDeleteGcnPublication}
                      />
                    </div>
                  </Paper>
                )}
                <Dialog
                  open={selectedGcnPublicationId !== null}
                  onClose={() => setSelectedGcnPublicationId(null)}
                  style={{ position: "fixed" }}
                  fullScreen
                >
                  <DialogTitle
                    onClose={() => setSelectedGcnPublicationId(null)}
                  >
                    Publication {dateobs}:{" "}
                    {gcnEvent?.publication?.id && (
                      <a
                        href={`/public/publications/gcn/${gcnEvent?.publication?.id}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {gcnEvent?.publication?.publication_name}
                      </a>
                    )}
                  </DialogTitle>
                  <DialogContent dividers>
                    {gcnEvent?.publication?.data && (
                      <GcnPublicationEdit publication={gcnEvent?.publication} />
                    )}
                  </DialogContent>
                </Dialog>
              </Grid>
            </Grid>
          </DialogContent>
        </Dialog>
      )}
    </>
  );
};

GcnPublication.propTypes = {
  dateobs: PropTypes.string.isRequired,
};

export default GcnPublication;
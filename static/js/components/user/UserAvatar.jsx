import React from "react";
import PropTypes from "prop-types";
import makeStyles from "@mui/styles/makeStyles";
import Avatar from "@mui/material/Avatar";
import Tooltip from "@mui/material/Tooltip";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import Badge from "@mui/material/Badge";

const useStyles = makeStyles((theme) => ({
  avatar: (props) => ({
    width: props.size,
    height: props.size,
    backgroundColor: props.usercolor,
    "&:after": {
      content: `"${props.backUpLetters}"`,
      color: theme.palette.getContrastText(props.usercolor),
      fontWeight: "bold",
      fontSize: `${Math.max(parseInt(parseFloat(props.size) / 3, 10), 10)}px`,
      position: "absolute",
    },
  }),
  avatarImg: {
    zIndex: 1,
  },
  badge: (props) => ({
    fontSize: `${Math.max(parseInt(parseFloat(props.size) / 1.8, 10), 10)}px`,
    color: "#555555",
  }),
}));

// Return true if all characters in a string are Korean characters
export const isAllKoreanCharacters = (str) =>
  str.match(
    /^([\uac00-\ud7af]|[\u1100-\u11ff]|[\u3130-\u318f]|[\ua960-\ua97f]|[\ud7b0-\ud7ff])+$/g,
  );

const getInitials = (firstName, lastName) => {
  // Korean last names are almost always <=2 characters; last names are written first,
  // so using the full first name is a more natural "initials" than (firstName[0], lastName[0])
  // also, first names have more chance to be unique as a lot of last names are very common
  if (isAllKoreanCharacters(firstName)) {
    return firstName;
  }
  return `${firstName?.charAt(0)}${lastName?.charAt(0)}`;
};

const UserAvatar = ({
  size,
  firstName,
  lastName,
  username,
  gravatarUrl,
  isBot,
}) => {
  // use the hash of the username (which is in the gravatarUrl) to
  // select a unique color for this user
  function bgcolor() {
    let hash = gravatarUrl.split("/");
    hash = hash[hash.length - 1];
    if (hash.length >= 6) {
      // make the color string with a slight transparency
      return `#${hash.slice(0, 6)}aa`;
    }
    return "#aaaaaaaa";
  }

  const usercolor = bgcolor();

  const backUpLetters =
    firstName === null
      ? username.slice(0, 2)
      : getInitials(firstName, lastName);

  const props = { size, usercolor, backUpLetters };
  const classes = useStyles(props);

  let tooltipText = username;
  if (firstName && lastName) {
    tooltipText += ` (${firstName} ${lastName})`;
  }
  if (isBot) {
    tooltipText = `[Bot] ${tooltipText}`;
  }

  if (isBot) {
    return (
      <Tooltip title={tooltipText} arrow placement="top-start">
        <Badge
          overlap="circular"
          anchorOrigin={{ vertical: "top", horizontal: "right" }}
          badgeContent={
            <SmartToyIcon fontSize="small" className={classes.badge} />
          }
        >
          <Avatar
            alt={backUpLetters}
            src={`${gravatarUrl}&s=${size}`}
            size={size}
            classes={{
              root: classes.avatar,
              img: classes.avatarImg,
            }}
          />
        </Badge>
      </Tooltip>
    );
  }

  return (
    <Tooltip title={tooltipText} arrow placement="top-start">
      <Avatar
        alt={backUpLetters}
        src={`${gravatarUrl}&s=${size}`}
        size={size}
        classes={{
          root: classes.avatar,
          img: classes.avatarImg,
        }}
      />
    </Tooltip>
  );
};

UserAvatar.propTypes = {
  size: PropTypes.number.isRequired,
  firstName: PropTypes.string,
  lastName: PropTypes.string,
  username: PropTypes.string.isRequired,
  gravatarUrl: PropTypes.string.isRequired,
  isBot: PropTypes.bool,
};

UserAvatar.defaultProps = {
  firstName: null,
  lastName: null,
  isBot: false,
};

export default UserAvatar;

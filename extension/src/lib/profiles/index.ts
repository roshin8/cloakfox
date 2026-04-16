/**
 * Profile Database Index
 *
 * Exports all profile-related utilities for user agents and screen sizes.
 */

export {
  type UserAgentProfile,
  ALL_PROFILES,
  PROFILES_BY_OS,
  PROFILES_BY_BROWSER,
  DESKTOP_PROFILES,
  MOBILE_PROFILES,
  getProfileById,
  getRandomProfile,
} from './user-agents';

export {
  type ScreenProfile,
  ALL_SCREENS,
  SCREENS_BY_CATEGORY,
  NON_TOUCH_SCREENS,
  TOUCH_SCREENS,
  getScreenById,
  getRandomScreen,
  getScreenForUserAgent,
  varyScreenProfile,
} from './screen-sizes';

# core/audio_manager.py

import pygame
import settings

class AudioManager:
    def __init__(self):
        """
        Initializes the audio manager.
        It pre-loads all sound effects and sets up the music channel.
        """
        # Ensure the mixer is initialized before use.
        if not pygame.mixer.get_init():
            pygame.mixer.init()

        self.sounds = {}
        self.music_volume = settings.MENU_MUSIC_VOLUME
        self.sfx_volume = 0.5  # Default volume for all sound effects.

        self._load_sounds()
        pygame.mixer.music.set_volume(self.music_volume)

    def _load_sounds(self):
        """
        Pre-loads all sound effects defined in settings into memory.
        This avoids loading from disk during gameplay.
        """
        # A dictionary mapping sound names to their file paths from settings.
        sound_paths = {
            'hover': settings.MENU_HOVER_SOUND_PATH,
            'tick': settings.BOMB_TICK_PATH,
            'explosion': settings.EXPLOSION_PATH,
            'bling': settings.BLING_PATH,
            'hurt': settings.HURT_PATH,
        }
        for name, path in sound_paths.items():
            try:
                self.sounds[name] = pygame.mixer.Sound(path)
            except pygame.error as e:
                print(f"Error loading sound '{name}' from '{path}': {e}")

    def stop_all_sounds(self):
        """Stops all currently playing sound effects."""
        for sound in self.sounds.values():
            sound.stop()
            
    def play_sound(self, name, loops=0, volume_multiplier=1.0):
        """
        Plays a pre-loaded sound effect by its name.

        Args:
            name (str): The key name of the sound to play.
            loops (int): The number of times to repeat the sound. 0 means play once, -1 means loop forever.
            volume_multiplier (float): A multiplier for the sound's volume (0.0 to 1.0).
        """
        if name in self.sounds:
            sound = self.sounds[name]
            sound.set_volume(self.sfx_volume * volume_multiplier)
            sound.play(loops=loops)
        else:
            print(f"Warning: Sound '{name}' not found in AudioManager.")

    def stop_sound(self, name):
        """
        Stops a specific sound effect from playing.
        Useful for looping sounds like the bomb tick.

        Args:
            name (str): The key name of the sound to stop.
        """
        if name in self.sounds:
            self.sounds[name].stop()
        else:
            print(f"Warning: Cannot stop sound '{name}', not found in AudioManager.")

    def play_music(self, music_path, loops=-1):
        """
        Loads and plays background music. Loading new music automatically stops the old one.

        Args:
            music_path (str): The file path to the music file.
            loops (int): The number of times to repeat the music. -1 means loop forever.
        """
        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.play(loops)
        except pygame.error as e:
            print(f"Error playing music from '{music_path}': {e}")

    def stop_music(self):
        """Stops the background music."""
        pygame.mixer.music.stop()

    def set_sfx_volume(self, volume):
        """
        Sets the base volume for all sound effects.

        Args:
            volume (float): A value from 0.0 (silent) to 1.0 (full volume).
        """
        self.sfx_volume = max(0.0, min(1.0, volume))

    def set_music_volume(self, volume):
        """
        Sets the volume for the background music.

        Args:
            volume (float): A value from 0.0 (silent) to 1.0 (full volume).
        """
        self.music_volume = max(0.0, min(1.0, volume))
        pygame.mixer.music.set_volume(self.music_volume)
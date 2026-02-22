# HeyStat - Fork Notice

## About HeyStat

**HeyStat** is a fork of [jamovi](https://www.jamovi.org) - a free and open statistical software.

This project was created to:
- Provide a Vietnamese-friendly deployment of statistical analysis tools
- Customize the platform for educational use at Vietnamese institutions
- Deploy as a web-based service accessible via modern browsers

## Original Project

**jamovi** - Free and Open Statistical Software
- Website: https://www.jamovi.org
- Source Code: https://github.com/jamovi/jamovi
- License: AGPL3 / GPL2+ (see [LICENSE.md](LICENSE.md))
- Authors: The jamovi team

## Fork Information

- **Fork Date**: December 2025
- **Based on**: jamovi 2.7.6
- **Maintainer**: HeyStat Team
- **Repository**: https://github.com/[your-org]/HeyStat

## Key Differences from jamovi

### Deployment Configuration
- Optimized for Apple Silicon (ARM64) macOS deployment
- Configured for web-based access with Cloudflare Tunnel
- Modified port configuration (42337-42339) to avoid conflicts
- Custom nginx reverse proxy setup

### Branding Changes
- Application name: jamovi → HeyStat
- Custom logo and visual identity
- Localized for Vietnamese users

### Infrastructure
- Docker-based deployment on Colima
- Auto-start LaunchDaemon configuration
- Isolated Documents folder for user data
- Production-ready security settings

## Compliance with Original License

HeyStat complies with jamovi's AGPL3/GPL2+ licenses by:

1. **Preserving All Original Copyright Notices**: All original jamovi copyright notices remain intact
2. **Source Code Availability**: This entire codebase is available under the same AGPL3/GPL2+ licenses
3. **License Compatibility**: All modifications are released under AGPL3, compatible with original
4. **Attribution**: This notice clearly identifies jamovi as the original project
5. **Changelog**: All modifications are documented in git history

## Copyright

### Original jamovi Copyright
- Copyright (C) 2016-2024 The jamovi team
- Licensed under AGPL3 / GPL2+ (see [LICENSE.md](LICENSE.md))

### HeyStat Modifications Copyright
- Copyright (C) 2025 HeyStat Team
- Licensed under AGPL3 (compatible with jamovi's license)
- All modifications are clearly documented in git history

## Trademark Notice

"jamovi" is a trademark of The jamovi Project. HeyStat is an independent fork and is not endorsed by or affiliated with The jamovi Project.

"HeyStat" is used as the application name for this fork to distinguish it from the original jamovi project.

## Contributing

If you want to contribute to:
- **Original jamovi**: See https://github.com/jamovi/jamovi and [CONTRIBUTING.md](CONTRIBUTING.md)
- **HeyStat fork**: Submit issues and pull requests to this repository

## Acknowledgments

We are deeply grateful to:
- **The jamovi team** for creating and maintaining excellent open-source statistical software
- **The R Project** and all R package developers whose work powers the statistical analyses
- **The open-source community** for the tools and libraries that make this possible

## Links

- **jamovi**: https://www.jamovi.org
- **jamovi Documentation**: https://www.jamovi.org/user-manual.html
- **jamovi Community**: https://forum.jamovi.org
- **HeyStat Deployment**: https://heystat.truyenthong.edu.vn

## License

This project (HeyStat) inherits the AGPL3/GPL2+ licenses from jamovi. See [LICENSE.md](LICENSE.md) for full license text.

```
HeyStat - A fork of jamovi
Copyright (C) 2025 HeyStat Team
Copyright (C) 2016-2024 The jamovi team

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.
```

---

**Last Updated**: December 15, 2025

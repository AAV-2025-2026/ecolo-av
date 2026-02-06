import 'package:flutter_pi/screens/home_page.dart';
import 'package:flutter_pi/screens/map_page.dart';

class SplitScreen extends StatefulWidget {
  @override
  _SplitScreenState createState() => _SplitScreenState();
}

class _SplitScreenState extends State<SplitScreen> {
  bool isFullScreen = false;
  String fullScreenPage = ""; // "map" or "home"

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text("Map + Home"),
        actions: [
          if (!isFullScreen) ...[
            IconButton(
              icon: Icon(Icons.map),
              onPressed: () {
                setState(() {
                  isFullScreen = true;
                  fullScreenPage = "map";
                });
              },
            ),
            IconButton(
              icon: Icon(Icons.home),
              onPressed: () {
                setState(() {
                  isFullScreen = true;
                  fullScreenPage = "home";
                });
              },
            ),
          ]
        ],
        leading: isFullScreen
            ? IconButton(
                icon: Icon(Icons.arrow_back),
                onPressed: () {
                  setState(() {
                    isFullScreen = false;
                    fullScreenPage = "";
                  });
                },
              )
            : null,
      ),
      body: isFullScreen
          ? _buildFullScreen()
          : _buildSplitScreen(),
    );
  }

  Widget _buildSplitScreen() {
    return Row(
      children: [
        Expanded(
          flex: 2,
          child: MapPage(), // your map widget
        ),
        Expanded(
          flex: 1,
          child: MyHomePage(title: 'UI Dashboard'),
        ),
      ],
    );
  }

  Widget _buildFullScreen() {
    if (fullScreenPage == "map") {
      return MapPage();
    } else if (fullScreenPage == "home") {
      return MyHomePage(title: 'UI Dashboard');
    }
    return Container();
  }
}
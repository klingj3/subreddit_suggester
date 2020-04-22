/*jshint esversion: 6 */

/* Submit an API call to get the most popular subreddits for a particular username */
function getSubreddits(username) {
    d3.select("#suggestion-table").remove();
    d3.select("#suggestion-message").remove();
    let mnt = d3.select('.results');
    if (!username) {
        mnt.append('div').attr('id', 'suggestion-message').text("Please provide a username");
        return;
    }
    let table = mnt.append("div").attr("id", "suggestion-table").style('opacity', 0);
    let header = table.append("div").attr("class", "tbl-header")
        .append("table")
        .append("thead")
        .append("tr");
    header.append("th").text("");
    header.append("th").text("Popularity");
    header.append("th").text("Subreddit");
    header.append("th").text("Confidence");
    table.transition().duration(1000).style("opacity", 1);
    table.append("div").attr("class", "tbl-content").append("table").append("div").attr("class", "loading-message")
        .text("loading");
    $.getJSON(`api/suggestions/${username}`, (response) => {
        // Remove old container for these suggestion values, if they exist.
        if (response && response.data) {
            d3.select('.tbl-content').remove();
            let content = table.append("div").attr("class", "tbl-content").append("table").append("tbody");
            response.data.forEach((entry, i) => {
                let row = content.append("tr").attr("onclick", `window.open('https://reddit.com/r/${entry[0]}')`);
                row.append("td").text(i+1);
                row.append("td").text(entry[2]);
                row.append("td").text(entry[0]);
                row.append("td").text(entry[1]);

            });
        } else {
            table.remove();
            mnt.append('div').attr('id', 'suggestion-message').text("An error was encountered in retrieving this" +
                "user's data. " + response.message ? response.message : '');
        }
    });
}

function generateBackground() {
    let canvas = d3.select("#canvas");
    let canvasDim = canvas.node().getBoundingClientRect();
    setInterval(() => {
        let sizeFactor = Math.max(Math.random(), 0.5);
        let x = canvasDim.width * Math.random(),
            y = canvasDim.height + 20;
        let initialRotation = Math.random() * 360;
        let imageContainer = canvas.append("img");
        imageContainer.attr("class", "image-container")
            .attr("src", "/static/img/arrow.svg")
            .attr("width", 45 * sizeFactor)
            .attr("height", 45 * sizeFactor)
            .style("transform", `rotate(${initialRotation}deg)`)
            .style("opacity", 0.5 * sizeFactor)
            .style("top", `${y}px`)
            .style("left", `${x}px`)
            .transition().duration(3000)
            .style("opacity", 0)
            .style("top", `${y - 200 * sizeFactor}px`)
            .style("transform", `rotate(${initialRotation + 90}deg)`)
            .remove()
        ;
    }, 200);
}

generateBackground();